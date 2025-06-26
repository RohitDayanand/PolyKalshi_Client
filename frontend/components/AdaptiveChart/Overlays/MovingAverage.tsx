import { LineSeries as LightweightLineSeries, ISeriesApi, LineData, Time } from 'lightweight-charts'
import SeriesClass from './BaseClass'
import { SeriesClassConstructorOptions, MarketDataUpdate, MarketDataPoint } from '../../../lib/ChartStuff/chart-types'

/**
 * MOVING AVERAGE OVERLAY COMPONENT
 * Extends BaseClass with configurable moving average calculations
 * Processes raw market data and displays smooth trend indicators
 */

interface MovingAverageOptions {
  period?: number
  color?: string
  lineWidth?: number
  lineStyle?: 0 | 1 | 2 | 3 // LineStyle enum values
  priceLineVisible?: boolean
  lastValueVisible?: boolean
  crosshairMarkerVisible?: boolean
}

// Default configuration for moving averages
const DEFAULT_MA_OPTIONS: Required<MovingAverageOptions> = {
  period: 20,
  color: '#90EE90', // Light green default
  lineWidth: 2,
  lineStyle: 2, // Dashed line
  priceLineVisible: false,
  lastValueVisible: false,
  crosshairMarkerVisible: true
}

export class MovingAverage extends SeriesClass {
  private lineSeriesApi: ISeriesApi<'Line'> | null = null
  private readonly options: Required<MovingAverageOptions>
  private rawDataBuffer: Array<{ time: any, value: number }> = []
  private maData: Array<{ time: any, value: number }> = []

  constructor(options: SeriesClassConstructorOptions & { movingAverageOptions?: MovingAverageOptions }) {
    console.trace("Created the moving average");
    super(options)
    
    // Initialize moving average options with defaults
    this.options = {
      ...DEFAULT_MA_OPTIONS,
      ...options.movingAverageOptions
    }
    
    // Override default color based on series type if not explicitly provided
    if (!options.movingAverageOptions?.color) {
      this.options.color = this.seriesType === 'YES' ? '#90EE90' : '#FFB6C1'
    }
    
    //Create the series in the subclass to stay consistant with design patterns 
    try {
      this.seriesApi = this.createSeries()
      console.log(`✅ SeriesClass - Created ${this.seriesType} series with subscription ID: ${this.subscriptionId}`)
      
      // Auto-subscribe to market data if subscription ID exists
      // Parse subscription ID to extract marketId, side, and timeRange
      if (this.subscriptionId) {
        console.log(`🔗 MovingAverage - Attempting subscription with ID: ${this.subscriptionId}`)
        
        // Parse subscription ID format: "seriesType&timeRange&marketId"
        const subscriptionParts = this.subscriptionId.split('&')
        if (subscriptionParts.length >= 3) {
          const [seriesTypeStr, timeRange, ...marketIdParts] = subscriptionParts
          const marketId = marketIdParts.join('&') // Rejoin market ID parts that may contain '&'
          const side = seriesTypeStr.toLowerCase() as 'yes' | 'no'
          
          console.log(`📊 MovingAverage - Parsed subscription details:`, {
            subscriptionId: this.subscriptionId,
            marketId,
            side,
            timeRange,
            seriesType: this.seriesType
          })
          
          this.subscribe(marketId, side, timeRange as any)
        } else {
          console.error(`❌ MovingAverage - Invalid subscription ID format: ${this.subscriptionId}`)
        }
      } else {
        console.warn(`⚠️ MovingAverage - No subscription ID provided for ${this.seriesType} series`)
      }
    } catch (error) {
      console.error(`❌ SeriesClass - Failed to create ${this.seriesType} series:`, error)
      this.onError(`Failed to create series: ${error}`)
    }

    console.log(`📈 MovingAverage - Initialized ${this.seriesType} moving average with ${this.options.period}-point period`)
  }

  // Implementation of abstract createSeries method
  createSeries(): ISeriesApi<'Line'> {
    try {
      // Create line series with configurable moving average styling
      this.lineSeriesApi = this.chartInstance.addSeries(LightweightLineSeries, {
        color: this.options.color,
        lineWidth: this.options.lineWidth as any,
        lineStyle: this.options.lineStyle,
        priceLineVisible: this.options.priceLineVisible,
        lastValueVisible: this.options.lastValueVisible,
        crosshairMarkerVisible: this.options.crosshairMarkerVisible,
        title: `${this.seriesType} MA(${this.options.period})`
      })

      console.log(`✅ MovingAverage - Created ${this.seriesType} moving average series with color: ${this.options.color}`)
      console.log(`🔗 MovingAverage - Will be stored in BaseClass.seriesApi for market data handling`)
      
      return this.lineSeriesApi
    } catch (error) {
      console.error(`❌ MovingAverage - Failed to create ${this.seriesType} moving average series:`, error)
      throw error
    }
  }

  /**
   * CUSTOM DATA PROCESSING: Override updateData for initial moving average calculation
   * Processes full dataset and calculates moving averages from scratch
   */
  protected updateData(data: Array<{ time: any, value: number }>): void {
    try {
      console.log(`📊 MovingAverage ${this.seriesType} - Processing ${data.length} data points for moving average calculation`)
      
      // Store raw data and calculate moving averages
      this.rawDataBuffer = [...data]
      this.maData = this.calculateMovingAverage(this.rawDataBuffer)
      
      // Update the chart series with calculated moving average data
      if (this.seriesApi && this.maData.length > 0) {
        this.seriesApi.setData(this.maData)
        console.log(`✅ MovingAverage ${this.seriesType} - Updated chart with ${this.maData.length} moving average points`)
      } else {
        console.log(`⚠️ MovingAverage ${this.seriesType} - Not enough data for moving average (need ${this.options.period} points, have ${this.rawDataBuffer.length})`)
      }
    } catch (error) {
      console.error(`❌ MovingAverage ${this.seriesType} - Failed to update moving average data:`, error)
      this.onError(`Moving average update failed: ${error}`)
    }
  }
  
  /**
   * CUSTOM DATA PROCESSING: Override appendData for real-time moving average updates
   * Efficiently updates moving average with new data point without recalculating everything
   */
  protected appendData(dataPoint: { time: any, value: number }): void {
    try {
      console.log(`📈 MovingAverage ${this.seriesType} - Processing new data point for moving average:`, dataPoint)
      
      // Add new point to raw data buffer
      this.rawDataBuffer.push(dataPoint)
      
      // Maintain buffer size if needed (optional optimization)
      const maxBufferSize = this.options.period * 10 // Keep 10x the period for smooth calculations
      if (this.rawDataBuffer.length > maxBufferSize) {
        this.rawDataBuffer = this.rawDataBuffer.slice(-maxBufferSize)
        console.log(`🧹 MovingAverage ${this.seriesType} - Trimmed buffer to ${maxBufferSize} points`)
      }
      
      // Calculate new moving average point if we have enough data
      if (this.rawDataBuffer.length >= this.options.period) {
        const newMAPoint = this.calculateSingleMovingAveragePoint(this.rawDataBuffer, this.rawDataBuffer.length - 1)
        
        if (newMAPoint) {
          // Add to our MA data
          this.maData.push(newMAPoint)
          
          // Update the chart series with new moving average point
          if (this.seriesApi) {
            this.seriesApi.update(newMAPoint)
            console.log(`✅ MovingAverage ${this.seriesType} - Appended moving average point:`, newMAPoint)
          }
        }
      } else {
        console.log(`⏳ MovingAverage ${this.seriesType} - Need ${this.options.period - this.rawDataBuffer.length} more points for moving average`)
      }
    } catch (error) {
      console.error(`❌ MovingAverage ${this.seriesType} - Failed to append moving average data:`, error)
      this.onError(`Moving average append failed: ${error}`)
    }
  }

  /**
   * MOVING AVERAGE CALCULATION: Calculate moving averages for full dataset
   * Returns array of moving average points starting from the period-th point
   */
  private calculateMovingAverage(data: Array<{ time: any, value: number }>): Array<{ time: any, value: number }> {
    const maData: Array<{ time: any, value: number }> = []

    // Calculate moving average starting from the period-th point
    for (let i = this.options.period - 1; i < data.length; i++) {
      const maPoint = this.calculateSingleMovingAveragePoint(data, i)
      if (maPoint) {
        maData.push(maPoint)
      }
    }
    
    console.log(`📊 MovingAverage ${this.seriesType} - Calculated ${maData.length} moving average points from ${data.length} raw data points`)
    return maData
  }

  /**
   * MOVING AVERAGE CALCULATION: Calculate single moving average point at specific index
   * Returns moving average value for the given index position
   */
  private calculateSingleMovingAveragePoint(data: Array<{ time: any, value: number }>, index: number): { time: any, value: number } | null {
    if (index < this.options.period - 1 || index >= data.length) {
      return null
    }
    
    // Calculate the moving average for the period ending at this index
    let sum = 0
    for (let j = 0; j < this.options.period; j++) {
      sum += data[index - j].value
    }
    const maValue = sum / this.options.period
    
    return {
      time: data[index].time,
      value: maValue
    }
  }

  /**
   * UTILITY: Get current moving average statistics
   * Returns information about the current state of the moving average
   */
  getMovingAverageStats(): { 
    period: number
    rawDataPoints: number
    maDataPoints: number
    latestMA: number | null
  } {
    const latestMA = this.maData.length > 0 ? this.maData[this.maData.length - 1].value : null
    
    return {
      period: this.options.period,
      rawDataPoints: this.rawDataBuffer.length,
      maDataPoints: this.maData.length,
      latestMA
    }
  }

  /**
   * CLEANUP: Override remove to clean up moving average specific data
   */
  remove(): void {
    console.log(`🧹 MovingAverage ${this.seriesType} - Cleaning up moving average data`)
    
    // Clear moving average specific data
    this.rawDataBuffer = []
    this.maData = []
    this.lineSeriesApi = null
    
    // Call parent cleanup
    super.remove()
    
    console.log(`✅ MovingAverage ${this.seriesType} - Moving average cleanup completed`)
  }
}

export default MovingAverage
