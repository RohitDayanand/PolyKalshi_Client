import { CandlestickSeries as LightweightCandlestickSeries, ISeriesApi, CandlestickData, Time } from 'lightweight-charts'
import SeriesClass from './BaseClass'
import { SeriesClassConstructorOptions, MarketDataUpdate, MarketDataPoint } from '../../../lib/ChartStuff/chart-types'
import {parseSubscriptionId} from '../utils/parseSubscriptionId'
import { DataPoint } from '@/lib/RxJSChannel'
import { OHLC } from '@/lib/RxJSChannel/types'

/**
 * CANDLESTICK OVERLAY COMPONENT
 * Extends BaseClass with configurable candlestick chart functionality
 * Converts price data into OHLC candles with time-based aggregation
 */

export interface CandlestickUpdateLength {
  '1H': number   // Update interval for hourly view (in milliseconds)
  '1W': number   // Update interval for weekly view (in milliseconds)
  '1M': number   // Update interval for monthly view (in milliseconds)
  '1Y': number   // Update interval for yearly view (in milliseconds)
}

interface CandleStickOptions {
  timeframe?: number | 'auto' // Time interval in milliseconds for candle aggregation, or 'auto' to derive from chart range
  updateLength?: CandlestickUpdateLength // Custom update intervals for different time ranges
  upColor?: string   // Color for bullish candles
  downColor?: string // Color for bearish candles
  borderUpColor?: string
  borderDownColor?: string
  wickUpColor?: string
  wickDownColor?: string
  borderVisible?: boolean
  wickVisible?: boolean
  priceLineVisible?: boolean
  lastValueVisible?: boolean
  title?: string
  // NO series specific colors
  noUpColor?: string     // Color for NO bullish candles
  noDownColor?: string   // Color for NO bearish candles
  noBorderUpColor?: string
  noBorderDownColor?: string
  noWickUpColor?: string
  noWickDownColor?: string
}

// Default update intervals for candlestick aggregation
const DEFAULT_CANDLESTICK_UPDATE_LENGTH: CandlestickUpdateLength = {
  '1H': 60 * 1000,        // 1-minute candles for hourly view
  '1W': 10 * 60 * 1000,   // 10-minute candles for weekly view
  '1M': 30 * 60 * 1000,   // 30-minute candles for monthly view
  '1Y': 24 * 60 * 60 * 1000 // 1-day candles for yearly view
}

// Default configuration for candlesticks
const DEFAULT_CANDLESTICK_OPTIONS: Required<Omit<CandleStickOptions, 'timeframe' | 'updateLength' | 'noUpColor' | 'noDownColor' | 'noBorderUpColor' | 'noBorderDownColor' | 'noWickUpColor' | 'noWickDownColor'>> & { 
  timeframe: number | 'auto'
  updateLength: CandlestickUpdateLength
  noUpColor: string
  noDownColor: string
  noBorderUpColor: string
  noBorderDownColor: string
  noWickUpColor: string
  noWickDownColor: string
} = {
  timeframe: 'auto',            // Auto-derive from chart range
  updateLength: DEFAULT_CANDLESTICK_UPDATE_LENGTH,
  upColor: '#26a69a',           // Green for bullish (YES)
  downColor: '#ef5350',         // Red for bearish (YES)
  borderUpColor: '#26a69a',
  borderDownColor: '#ef5350',
  wickUpColor: '#26a69a',
  wickDownColor: '#ef5350',
  // NO series colors
  noUpColor: '#3b82f6',         // Blue for NO bullish
  noDownColor: '#f59e0b',       // Orange for NO bearish
  noBorderUpColor: '#3b82f6',
  noBorderDownColor: '#f59e0b',
  noWickUpColor: '#3b82f6',
  noWickDownColor: '#f59e0b',
  borderVisible: true,
  wickVisible: true,
  priceLineVisible: true,
  lastValueVisible: true,
  title: 'Candlesticks'
}

interface CandleData {
  time: number
  open: number
  high: number
  low: number
  close: number
  startTime: number
  endTime: number
  priceCount: number
}

export class CandleStick extends SeriesClass {
  private candlestickSeriesApi: ISeriesApi<'Candlestick'> | null = null
  private readonly options: Required<Omit<CandleStickOptions, 'timeframe' | 'updateLength' | 'noUpColor' | 'noDownColor' | 'noBorderUpColor' | 'noBorderDownColor' | 'noWickUpColor' | 'noWickDownColor'>> & { 
    timeframe: number | 'auto'
    updateLength: CandlestickUpdateLength
    noUpColor: string
    noDownColor: string
    noBorderUpColor: string
    noBorderDownColor: string
    noWickUpColor: string
    noWickDownColor: string
  }
  private rawDataBuffer: Array<{ time: any, value: number }> = []
  private candleBuffer: Map<number, CandleData> = new Map() // Key: candle start time
  private candleData: Array<CandlestickData> = []
  private currentTimeframe: number = 60 * 1000 // Actual timeframe in ms, default 1 minute

  constructor(options: SeriesClassConstructorOptions & { candleStickOptions?: CandleStickOptions }) {
    super(options)
    
    // Initialize candlestick options with defaults
    this.options = {
      ...DEFAULT_CANDLESTICK_OPTIONS,
      ...options.candleStickOptions
    }
    
    // Override default colors based on series type if not explicitly provided
    if (!options.candleStickOptions?.upColor && !options.candleStickOptions?.downColor) {
      if (this.seriesType === 'YES') {
        this.options.upColor = '#22c55e'    // Green for YES bullish
        this.options.downColor = '#ef4444'  // Red for YES bearish
        this.options.borderUpColor = '#22c55e'
        this.options.borderDownColor = '#ef4444'
        this.options.wickUpColor = '#22c55e'
        this.options.wickDownColor = '#ef4444'
      } else if (this.seriesType === 'NO') {
        // Use NO-specific colors
        this.options.upColor = this.options.noUpColor
        this.options.downColor = this.options.noDownColor
        this.options.borderUpColor = this.options.noBorderUpColor
        this.options.borderDownColor = this.options.noBorderDownColor
        this.options.wickUpColor = this.options.noWickUpColor
        this.options.wickDownColor = this.options.noWickDownColor
      } else {
        // Default colors for other series types
        this.options.upColor = '#3b82f6'    // Blue for other bullish
        this.options.downColor = '#f59e0b'  // Orange for other bearish
        this.options.borderUpColor = '#3b82f6'
        this.options.borderDownColor = '#f59e0b'
        this.options.wickUpColor = '#3b82f6'
        this.options.wickDownColor = '#f59e0b'
      }
    }
    
    // Set title with series type if not provided
    if (!options.candleStickOptions?.title) {
      this.options.title = `${this.seriesType} Candlesticks`
    }
    
    // Resolve timeframe: either use provided value or auto-derive from subscription ID
    this.currentTimeframe = this.resolveTimeframe()
    
    //Create the series in the subclass to stay consistent with design patterns 
    try {
      this.seriesApi = this.createSeries()
      console.log(`✅ CandleStick - Created ${this.seriesType} candlestick series with subscription ID: ${this.subscriptionId}`)
      
      // Auto-subscribe to market data if subscription ID exists
      // Parse subscription ID to extract marketId, side, and timeRange
      if (this.subscriptionId) {
        const newSubscriptionId = parseSubscriptionId(this.subscriptionId)
        if (newSubscriptionId) {
        console.log(`🔗 CandleStick - Attempting subscription with ID: ${this.subscriptionId}`)
        
          // Parse subscription ID format: "seriesType&timeRange&marketId"
          const {marketId, side, timeRange} = newSubscriptionId
          
          console.log(`📊 CandleStick - Parsed subscription details:`, {
            subscriptionId: this.subscriptionId,
            marketId,
            side,
            timeRange,
            seriesType: this.seriesType
          })
          
          this.subscribe(marketId, side, timeRange as any)
        } else {
          console.error(`❌ CandleStick - Invalid parsed subscription ID format: ${this.subscriptionId}`)
        }
      } else {
        console.warn(`⚠️ CandleStick - No subscription ID provided for ${this.seriesType} series`)
      }
    } catch (error) {
      console.error(`❌ CandleStick - Failed to create ${this.seriesType} series:`, error)
      this.onError(`Failed to create candlestick series: ${error}`)
    }

    console.log(`📊 CandleStick - Initialized ${this.seriesType} candlesticks with ${this.currentTimeframe}ms timeframe`)
  }

  // Implementation of abstract createSeries method
  createSeries(): ISeriesApi<'Candlestick'> {
    try {
      // Create candlestick series with configurable styling
      this.candlestickSeriesApi = this.chartInstance.addSeries(LightweightCandlestickSeries, {
        upColor: this.options.upColor,
        downColor: this.options.downColor,
        borderUpColor: this.options.borderUpColor,
        borderDownColor: this.options.borderDownColor,
        wickUpColor: this.options.wickUpColor,
        wickDownColor: this.options.wickDownColor,
        borderVisible: this.options.borderVisible,
        wickVisible: this.options.wickVisible,
        priceLineVisible: this.options.priceLineVisible,
        lastValueVisible: this.options.lastValueVisible,
        title: this.options.title
      })

      console.log(`✅ CandleStick - Created ${this.seriesType} candlestick series with colors: up=${this.options.upColor}, down=${this.options.downColor}`)
      console.log(`🔗 CandleStick - Will be stored in BaseClass.seriesApi for market data handling`)
      
      return this.candlestickSeriesApi
    } catch (error) {
      console.error(`❌ CandleStick - Failed to create ${this.seriesType} candlestick series:`, error)
      throw error
    }
  }

  /*
  @overide
  Override the mapping logic in base class to get the candlestick data from historical candlesticks
  */
  protected mapDataPointsToChartData(dataPoints: DataPoint[]): any[] {
    return dataPoints.map(point => ({
      open: point.candlestick?.open,
      high: point.candlestick?.high,
      low: point.candlestick?.low,
      close: point.candlestick?.close,
      time: point.time as any
    }))
  }


  /**
   * CUSTOM DATA PROCESSING: Override updateData for initial candlestick calculation
   * Processes full dataset and converts price points into OHLC candles
   * IseriesAPI accepts different formats for timestamps, so we are type flexible on this to process
   * different variants
   */
  protected updateData(data: any[]): void {
    try {
      console.log(`📊 CandleStick ${this.seriesType} - Processing ${data.length} price points for candlestick aggregation`)
      this.candlestickSeriesApi?.setData(data)
    }
    catch (error) {

    }
      
  }
  
  /**
   * CUSTOM DATA PROCESSING: Override appendData for real-time candlestick updates
   * Efficiently updates current candle or creates new candle based on timeframe
   */
  protected appendData(dataPoint: { time: any, value: number }): void {

    try {
      console.log(`📈 CandleStick ${this.seriesType} - Processing new price point:`, dataPoint)
      
      // Add new point to raw data buffer
      this.rawDataBuffer.push(dataPoint)
      
      // Get timestamp from dataPoint (convert if needed)
      const timestamp = typeof dataPoint.time === 'number' ? dataPoint.time * 1000 : new Date(dataPoint.time).getTime()
      
      // Determine which candle this point belongs to
      const candleStartTime = this.getCandleStartTime(timestamp)
      
      // Update or create candle
      const updatedCandle = this.updateOrCreateCandle(candleStartTime, timestamp, dataPoint.value)
      
      if (updatedCandle) {
        // Convert to LightweightCharts format
        const lightweightCandle: CandlestickData = {
          time: (updatedCandle.startTime / 1000) as Time,
          open: updatedCandle.open,
          high: updatedCandle.high,
          low: updatedCandle.low,
          close: updatedCandle.close
        }
        
        // Update or append to chart
        if (this.seriesApi) {
          // Check if this is updating the last candle or adding a new one
          const isNewCandle = this.candleData.length === 0 || 
                             (this.candleData[this.candleData.length - 1].time as number) < (lightweightCandle.time as number)
          
          if (isNewCandle) {
            // Add new candle to our data array
            this.candleData.push(lightweightCandle)
            console.log(`📊 CandleStick ${this.seriesType} - Added new candle:`, lightweightCandle)
          } else {
            // Update existing candle in our data array
            this.candleData[this.candleData.length - 1] = lightweightCandle
            console.log(`🔄 CandleStick ${this.seriesType} - Updated current candle:`, lightweightCandle)
          }
          
          // Update the chart
          this.seriesApi.update(lightweightCandle)
        }
      }
    } catch (error) {
      console.error(`❌ CandleStick ${this.seriesType} - Failed to append candlestick data:`, error)
      this.onError(`Candlestick append failed: ${error}`)
    }
  }

  /**
   * CANDLE AGGREGATION: Convert price data into OHLC candles
   * Groups price points by timeframe and calculates OHLC values
   */
  private aggregateDataIntoCandles(data: Array<{ time: any, value: number }>): Array<CandlestickData> {
    this.candleBuffer.clear()
    
    // Process each price point
    data.forEach(point => {
      const timestamp = typeof point.time === 'number' ? point.time * 1000 : new Date(point.time).getTime()
      const candleStartTime = this.getCandleStartTime(timestamp)
      
      this.updateOrCreateCandle(candleStartTime, timestamp, point.value)
    })
    
    // Convert to LightweightCharts format and sort by time
    const candles: Array<CandlestickData> = Array.from(this.candleBuffer.values())
      .sort((a, b) => a.startTime - b.startTime)
      .map(candle => ({
        time: (candle.startTime / 1000) as Time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close
      }))
    
    console.log(`📊 CandleStick ${this.seriesType} - Aggregated ${data.length} price points into ${candles.length} candles`)
    return candles
  }

  private getCandleStartTime(timestamp: number): number {
    return Math.floor(timestamp / this.currentTimeframe) * this.currentTimeframe
  }

  /**
   * CANDLE CALCULATION: Update existing candle or create new one
   */
  private updateOrCreateCandle(candleStartTime: number, timestamp: number, price: number): CandleData | null {
    let candle = this.candleBuffer.get(candleStartTime)
    
    if (!candle) {
      // Create new candle
      candle = {
        time: timestamp,
        open: price,
        high: price,
        low: price,
        close: price,
        startTime: candleStartTime,
        endTime: candleStartTime + this.currentTimeframe,
        priceCount: 1
      }
      this.candleBuffer.set(candleStartTime, candle)
    } else {
      // Update existing candle
      candle.high = Math.max(candle.high, price)
      candle.low = Math.min(candle.low, price)
      candle.close = price // Most recent price becomes close
      candle.time = timestamp // Update timestamp to most recent
      candle.priceCount++
    }
    
    return candle
  }

  /**
   * TIMEFRAME RESOLUTION: Resolve timeframe based on subscription ID or use provided value
   * Uses the new CandlestickUpdateLength interface for configurable intervals
   */
  private resolveTimeframe(): number {
    // If explicit timeframe provided, use it
    if (typeof this.options.timeframe === 'number') {
      return this.options.timeframe
    }
    
    // Auto-derive timeframe from subscription ID pattern using updateLength config
    if (this.subscriptionId) {
      if (this.subscriptionId.includes('1H')) {
        return this.options.updateLength['1H']
      } else if (this.subscriptionId.includes('1D')) {
        return 15 * 60 * 1000    // 15-minute candles for daily view
      } else if (this.subscriptionId.includes('1W')) {
        return this.options.updateLength['1W']
      } else if (this.subscriptionId.includes('1M')) {
        return this.options.updateLength['1M']
      } else if (this.subscriptionId.includes('1Y')) {
        return this.options.updateLength['1Y']
      }
    }
    
    // Default fallback - shorter timeframe for better density
    return 2 * 60 * 1000 // 2-minute candles
  }

  /**
   * UTILITY: Get current candlestick statistics
   */
  getCandleStickStats(): { 
    timeframe: number
    rawDataPoints: number
    candleCount: number
    latestCandle: CandlestickData | null
  } {
    const latestCandle = this.candleData.length > 0 ? this.candleData[this.candleData.length - 1] : null
    
    return {
      timeframe: this.currentTimeframe,
      rawDataPoints: this.rawDataBuffer.length,
      candleCount: this.candleData.length,
      latestCandle
    }
  }


  /**
   * UTILITY: Change timeframe and re-aggregate data
   */
  setTimeframe(newTimeframe: number): void {
    console.log(`🔄 CandleStick ${this.seriesType} - Changing timeframe from ${this.currentTimeframe}ms to ${newTimeframe}ms`)
    
    this.currentTimeframe = newTimeframe
    
    // Re-aggregate existing data with new timeframe
    if (this.rawDataBuffer.length > 0) {
      this.updateData(this.rawDataBuffer)
    }
  }

  /**
   * CLEANUP: Override remove to clean up candlestick specific data
   */
  remove(): void {
    console.log(`🧹 CandleStick ${this.seriesType} - Cleaning up candlestick data`)
    
    // Clear candlestick specific data
    this.rawDataBuffer = []
    this.candleBuffer.clear()
    this.candleData = []
    this.candlestickSeriesApi = null
    
    // Call parent cleanup
    super.remove()
    
    console.log(`✅ CandleStick ${this.seriesType} - Candlestick cleanup completed`)
  }
}

export default CandleStick