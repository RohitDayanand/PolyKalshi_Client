import { HistogramSeries as LightweightHistogramSeries, ISeriesApi, HistogramData, Time } from 'lightweight-charts'
import SeriesClass from './BaseClass'
import { SeriesClassConstructorOptions, MarketDataUpdate, MarketDataPoint } from '../../../lib/ChartStuff/chart-types'
import { CHART_THEME } from '@/lib/ChartStuff/chart-config'
import { parseSubscriptionId } from '../utils/parseSubscriptionId'

/**
 * VOLUME OVERLAY COMPONENT
 * Extends BaseClass with volume bars positioned at bottom 20% of chart
 * Generates volume data based on price change magnitude with green/red coloring
 */

interface VolumeOptions {
  baseVolumeMultiplier?: number
  volatilityMultiplier?: number
  color?: {
    up: string
    down: string
  }
  priceScaleVisible?: boolean
  lastValueVisible?: boolean
}

// Default configuration for volume display
const DEFAULT_VOLUME_OPTIONS: Required<VolumeOptions> = {
  baseVolumeMultiplier: 1000, // Base volume multiplier
  volatilityMultiplier: 5000, // Additional volume based on price change
  color: {
    up: '#4a5d4fAA',   // Muted grey-green with 67% opacity (AA = 170/255 ≈ 67%)
    down: '#5d4a4aAA'  // Muted grey-red with 67% opacity
  },
  priceScaleVisible: true, // Show scale to visualize volume values
  lastValueVisible: true   // Show latest volume value
}

export class Volume extends SeriesClass {
  private histogramSeriesApi: ISeriesApi<'Histogram'> | null = null
  private readonly options: Required<VolumeOptions>
  private rawDataBuffer: Array<{ time: any, value: number }> = []
  private volumeData: Array<HistogramData> = []
  private previousPrice: number | null = null

  constructor(options: SeriesClassConstructorOptions & { volumeOptions?: VolumeOptions }) {
    console.trace("Created the volume overlay");
    super(options)
    
    // Initialize volume options with defaults and theme colors
    this.options = {
      ...DEFAULT_VOLUME_OPTIONS,
      ...options.volumeOptions,
      color: {
        up: options.volumeOptions?.color?.up || CHART_THEME.colors.accent.green,
        down: options.volumeOptions?.color?.down || CHART_THEME.colors.accent.red
      }
    }
    
    // Create the series in the subclass to stay consistent with design patterns 
    try {
      this.seriesApi = this.createSeries()
      console.log(`✅ SeriesClass - Created ${this.seriesType} volume series with subscription ID: ${this.subscriptionId}`)
      
      // Auto-subscribe to market data if subscription ID exists
      if (this.subscriptionId) {
        console.log(`🔗 Volume - Attempting subscription with ID: ${this.subscriptionId}`)
        
        // Parse subscription ID using utility function
        const parsed = parseSubscriptionId(this.subscriptionId)
        if (parsed) {
          const { marketId, side, timeRange } = parsed
          
          console.log(`📊 Volume - Parsed subscription details:`, {
            subscriptionId: this.subscriptionId,
            marketId,
            side,
            timeRange,
            seriesType: this.seriesType
          })
          
          this.subscribe(marketId, side, timeRange as any)
        } else {
          console.error(`❌ Volume - Invalid subscription ID format: ${this.subscriptionId}`)
        }
      } else {
        console.warn(`⚠️ Volume - No subscription ID provided for ${this.seriesType} series`)
      }
    } catch (error) {
      console.error(`❌ SeriesClass - Failed to create ${this.seriesType} volume series:`, error)
      this.onError(`Failed to create volume series: ${error}`)
    }

    console.log(`📊 Volume - Initialized ${this.seriesType} volume overlay with theme colors`)
  }

  // Implementation of abstract createSeries method
  createSeries(): ISeriesApi<'Histogram'> {
    try {
      // Create histogram series for volume bars positioned at bottom 20%
      this.histogramSeriesApi = this.chartInstance.addSeries(LightweightHistogramSeries, {
        color: this.options.color.up, // Default color, will be overridden per bar
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: 'volume', // Separate price scale for volume
        lastValueVisible: this.options.lastValueVisible,
        title: `${this.seriesType} Volume`
      })

      // Configure the volume price scale for visibility and positioning
      this.chartInstance.priceScale('volume').applyOptions({
        scaleMargins: {
          top: 0.8, // Volume occupies bottom 20%
          bottom: 0.0,
        },
        visible: this.options.priceScaleVisible, // Show scale to visualize volume values
        borderVisible: true, // Show scale border
        textColor: '#666666', // Darker text for better visibility
        borderColor: '#333333', // Dark border
      })

      console.log(`✅ Volume - Created ${this.seriesType} volume histogram series with separate price scale`)
      console.log(`🔗 Volume - Will be stored in BaseClass.seriesApi for market data handling`)
      
      return this.histogramSeriesApi
    } catch (error) {
      console.error(`❌ Volume - Failed to create ${this.seriesType} volume series:`, error)
      throw error
    }
  }

  /**
   * CUSTOM DATA PROCESSING: Override updateData for initial volume calculation
   * Processes full dataset and calculates volume based on price changes
   */
  protected updateData(data: Array<{ time: any, value: number }>): void {
    try {
      console.log(`📊 Volume ${this.seriesType} - Processing ${data.length} data points for volume calculation`)
      
      // Store raw data and calculate volume data
      this.rawDataBuffer = [...data]
      this.volumeData = this.calculateVolumeData(this.rawDataBuffer)
      
      // Update the chart series with calculated volume data
      if (this.seriesApi && this.volumeData.length > 0) {
        this.seriesApi.setData(this.volumeData)
        console.log(`✅ Volume ${this.seriesType} - Updated chart with ${this.volumeData.length} volume bars`)
      } else {
        console.log(`⚠️ Volume ${this.seriesType} - No volume data to display`)
      }
    } catch (error) {
      console.error(`❌ Volume ${this.seriesType} - Failed to update volume data:`, error)
      this.onError(`Volume update failed: ${error}`)
    }
  }
  
  /**
   * CUSTOM DATA PROCESSING: Override appendData for real-time volume updates
   * Efficiently calculates volume for new data point based on price change
   */
  protected appendData(dataPoint: { time: any, value: number }): void {
    try {
      console.log(`📈 Volume ${this.seriesType} - Processing new data point for volume:`, dataPoint)
      
      // Add new point to raw data buffer
      this.rawDataBuffer.push(dataPoint)
      
      // Calculate volume for the new data point
      const volumePoint = this.calculateSingleVolumePoint(dataPoint)
      
      if (volumePoint) {
        // Add to our volume data
        this.volumeData.push(volumePoint)
        
        // Update the chart series with new volume bar
        if (this.seriesApi) {
          this.seriesApi.update(volumePoint)
          console.log(`✅ Volume ${this.seriesType} - Appended volume bar:`, volumePoint)
        }
      }
      
      // Update previous price for next calculation
      this.previousPrice = dataPoint.value
      
    } catch (error) {
      console.error(`❌ Volume ${this.seriesType} - Failed to append volume data:`, error)
      this.onError(`Volume append failed: ${error}`)
    }
  }

  /**
   * VOLUME CALCULATION: Calculate volume data for full dataset
   * Returns array of histogram data with green/red coloring based on price direction
   */
  private calculateVolumeData(data: Array<{ time: any, value: number }>): Array<HistogramData> {
    const volumeData: Array<HistogramData> = []
    let previousPrice: number | null = null

    for (let i = 0; i < data.length; i++) {
      const currentPrice = data[i].value
      const currentTime = data[i].time
      
      // Calculate volume based on price change magnitude
      let volume = this.options.baseVolumeMultiplier
      let color = this.options.color.up // Default to up color
      
      if (previousPrice !== null) {
        const priceChange = Math.abs(currentPrice - previousPrice)
        const priceDirection = currentPrice >= previousPrice
        
        // Add volatility-based volume
        volume += priceChange * this.options.volatilityMultiplier
        
        // Add some randomness (±20%) for realism
        const randomMultiplier = 0.8 + Math.random() * 0.4
        volume *= randomMultiplier
        
        // Set color based on price direction with darker, translucent colors
        color = priceDirection ? this.options.color.up : this.options.color.down
      }
      
      // Ensure minimum volume and round to integer
      volume = Math.max(Math.round(volume), this.options.baseVolumeMultiplier / 2)
      
      volumeData.push({
        time: currentTime,
        value: volume,
        color: color
      } as HistogramData)
      
      previousPrice = currentPrice
    }
    
    console.log(`📊 Volume ${this.seriesType} - Calculated ${volumeData.length} volume bars from ${data.length} price points`)
    return volumeData
  }

  /**
   * VOLUME CALCULATION: Calculate single volume bar for new price point
   * Returns histogram data with appropriate color based on price direction
   */
  private calculateSingleVolumePoint(dataPoint: { time: any, value: number }): HistogramData | null {
    try {
      const currentPrice = dataPoint.value
      const currentTime = dataPoint.time
      
      // Calculate volume based on price change magnitude
      let volume = this.options.baseVolumeMultiplier
      let color = this.options.color.up // Default to up color
      
      if (this.previousPrice !== null) {
        const priceChange = Math.abs(currentPrice - this.previousPrice)
        const priceDirection = currentPrice >= this.previousPrice
        
        // Add volatility-based volume
        volume += priceChange * this.options.volatilityMultiplier
        
        // Add some randomness (±20%) for realism
        const randomMultiplier = 0.8 + Math.random() * 0.4
        volume *= randomMultiplier
        
        // Set color based on price direction with darker, translucent colors
        color = priceDirection ? this.options.color.up : this.options.color.down
      }
      
      // Ensure minimum volume and round to integer
      volume = Math.max(Math.round(volume), this.options.baseVolumeMultiplier / 2)
      
      return {
        time: currentTime,
        value: volume,
        color: color
      } as HistogramData
      
    } catch (error) {
      console.error(`❌ Volume ${this.seriesType} - Failed to calculate volume point:`, error)
      return null
    }
  }

  /**
   * UTILITY: Get current volume statistics
   * Returns information about the current state of the volume overlay
   */
  getVolumeStats(): { 
    rawDataPoints: number
    volumeDataPoints: number
    latestVolume: number | null
    averageVolume: number | null
  } {
    const latestVolume = this.volumeData.length > 0 ? this.volumeData[this.volumeData.length - 1].value : null
    
    let averageVolume = null
    if (this.volumeData.length > 0) {
      const totalVolume = this.volumeData.reduce((sum, point) => sum + point.value, 0)
      averageVolume = totalVolume / this.volumeData.length
    }
    
    return {
      rawDataPoints: this.rawDataBuffer.length,
      volumeDataPoints: this.volumeData.length,
      latestVolume,
      averageVolume
    }
  }

  /**
   * CLEANUP: Override remove to clean up volume specific data
   */
  remove(): void {
    console.log(`🧹 Volume ${this.seriesType} - Cleaning up volume data`)
    
    // Clear volume specific data
    this.rawDataBuffer = []
    this.volumeData = []
    this.previousPrice = null
    this.histogramSeriesApi = null
    
    // Call parent cleanup
    super.remove()
    
    console.log(`✅ Volume ${this.seriesType} - Volume cleanup completed`)
  }
}

export default Volume
