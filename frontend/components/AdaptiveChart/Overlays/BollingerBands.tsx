import { LineSeries as LightweightLineSeries, ISeriesApi, LineData, Time } from 'lightweight-charts'
import SeriesClass from './BaseClass'
import { SeriesClassConstructorOptions, MarketDataUpdate, MarketDataPoint } from '../../../lib/ChartStuff/chart-types'

/**
 * BOLLINGER BANDS OVERLAY COMPONENT
 * Extends BaseClass with configurable Bollinger Bands calculations
 * Creates upper and lower bands based on moving average and standard deviation
 */

interface BollingerBandsOptions {
  period?: number
  standardDeviations?: number
  upperBandColor?: string
  lowerBandColor?: string
  lineWidth?: number
  lineStyle?: 0 | 1 | 2 | 3 // LineStyle enum values
  priceLineVisible?: boolean
  lastValueVisible?: boolean
  crosshairMarkerVisible?: boolean
}

// Default configuration for Bollinger Bands
const DEFAULT_BB_OPTIONS: Required<BollingerBandsOptions> = {
  period: 20,
  standardDeviations: 2,
  upperBandColor: '#808080', // Grey
  lowerBandColor: '#808080', // Grey
  lineWidth: 1,
  lineStyle: 0, // Solid line
  priceLineVisible: false,
  lastValueVisible: false,
  crosshairMarkerVisible: true
}

export class BollingerBands extends SeriesClass {
  private upperBandSeriesApi: ISeriesApi<'Line'> | null = null
  private lowerBandSeriesApi: ISeriesApi<'Line'> | null = null
  private readonly options: Required<BollingerBandsOptions>
  private rawDataBuffer: Array<{ time: any, value: number }> = []
  private upperBandData: Array<{ time: any, value: number }> = []
  private lowerBandData: Array<{ time: any, value: number }> = []

  constructor(options: SeriesClassConstructorOptions & { bollingerBandsOptions?: BollingerBandsOptions }) {
    super(options)
    
    // Initialize Bollinger Bands options with defaults
    this.options = {
      ...DEFAULT_BB_OPTIONS,
      ...options.bollingerBandsOptions
    }
    
    // Create the series in the subclass to stay consistent with design patterns 
    try {
      this.seriesApi = this.createSeries()
      console.log(`✅ SeriesClass - Created ${this.seriesType} Bollinger Bands with subscription ID: ${this.subscriptionId}`)
      
      // Auto-subscribe to market data if subscription ID exists
      // Parse subscription ID to extract marketId, side, and timeRange
      if (this.subscriptionId) {
        console.log(`🔗 BollingerBands - Attempting subscription with ID: ${this.subscriptionId}`)
        
        // Parse subscription ID format: "seriesType&timeRange&marketId"
        const subscriptionParts = this.subscriptionId.split('&')
        if (subscriptionParts.length >= 3) {
          const [seriesTypeStr, timeRange, ...marketIdParts] = subscriptionParts
          const marketId = marketIdParts.join('&') // Rejoin market ID parts that may contain '&'
          const side = seriesTypeStr.toLowerCase() as 'yes' | 'no'
          
          console.log(`📊 BollingerBands - Parsed subscription details:`, {
            subscriptionId: this.subscriptionId,
            marketId,
            side,
            timeRange,
            seriesType: this.seriesType
          })
          
          this.subscribe(marketId, side, timeRange as any)
        } else {
          console.error(`❌ BollingerBands - Invalid subscription ID format: ${this.subscriptionId}`)
        }
      } else {
        console.warn(`⚠️ BollingerBands - No subscription ID provided for ${this.seriesType} series`)
      }
    } catch (error) {
      console.error(`❌ SeriesClass - Failed to create ${this.seriesType} Bollinger Bands:`, error)
      this.onError(`Failed to create Bollinger Bands: ${error}`)
    }

    console.log(`📈 BollingerBands - Initialized ${this.seriesType} Bollinger Bands with ${this.options.period}-period, ${this.options.standardDeviations}σ`)
  }

  // Implementation of abstract createSeries method
  createSeries(): ISeriesApi<'Line'> {
    try {
      // Create upper band series
      this.upperBandSeriesApi = this.chartInstance.addSeries(LightweightLineSeries, {
        color: this.options.upperBandColor,
        lineWidth: this.options.lineWidth as any,
        lineStyle: this.options.lineStyle,
        priceLineVisible: this.options.priceLineVisible,
        lastValueVisible: this.options.lastValueVisible,
        crosshairMarkerVisible: this.options.crosshairMarkerVisible,
        title: `${this.seriesType} BB Upper(${this.options.period},${this.options.standardDeviations})`
      })

      // Create lower band series
      this.lowerBandSeriesApi = this.chartInstance.addSeries(LightweightLineSeries, {
        color: this.options.lowerBandColor,
        lineWidth: this.options.lineWidth as any,
        lineStyle: this.options.lineStyle,
        priceLineVisible: this.options.priceLineVisible,
        lastValueVisible: this.options.lastValueVisible,
        crosshairMarkerVisible: this.options.crosshairMarkerVisible,
        title: `${this.seriesType} BB Lower(${this.options.period},${this.options.standardDeviations})`
      })

      console.log(`✅ BollingerBands - Created ${this.seriesType} Bollinger Bands series with colors: ${this.options.upperBandColor}, ${this.options.lowerBandColor}`)
      
      // Return upper band as the main series (BaseClass requirement)
      return this.upperBandSeriesApi
    } catch (error) {
      console.error(`❌ BollingerBands - Failed to create ${this.seriesType} Bollinger Bands series:`, error)
      throw error
    }
  }

  /**
   * CUSTOM DATA PROCESSING: Override updateData for initial Bollinger Bands calculation
   * Processes full dataset and calculates Bollinger Bands from scratch
   */
  protected updateData(data: Array<{ time: any, value: number }>): void {
    try {
      // Store raw data and calculate Bollinger Bands
      this.rawDataBuffer = [...data]
      const bollingerData = this.calculateBollingerBands(this.rawDataBuffer)
      
      this.upperBandData = bollingerData.upperBand
      this.lowerBandData = bollingerData.lowerBand
      
      // Update both chart series with calculated Bollinger Bands data
      if (this.upperBandSeriesApi && this.lowerBandSeriesApi && this.upperBandData.length > 0) {
        console.log(`UpperBandData is ${this.upperBandData ?? 'ERROR: NULL DETECTED'}, LowerBandData is ${this.lowerBandData ?? 'ERROR: NULL DETECTED'}`)
        debugger;
        this.upperBandSeriesApi.setData(this.upperBandData)
        this.lowerBandSeriesApi.setData(this.lowerBandData)
        console.log(`✅ BollingerBands ${this.seriesType} - Updated chart with ${this.upperBandData.length} Bollinger Bands points`)
      } else {
        console.log(`⚠️ BollingerBands ${this.seriesType} - Not enough data for Bollinger Bands (need ${this.options.period} points, have ${this.rawDataBuffer.length})`)
      }
    } catch (error) {
      console.error(`❌ BollingerBands ${this.seriesType} - Failed to update Bollinger Bands data:`, error)
      this.onError(`Bollinger Bands update failed: ${error}`)
    }
  }
  
  /**
   * CUSTOM DATA PROCESSING: Override appendData for real-time Bollinger Bands updates
   * Efficiently updates Bollinger Bands with new data point without recalculating everything
   */
  protected appendData(dataPoint: { time: any, value: number }): void {
    try {
      // Add new point to raw data buffer
      this.rawDataBuffer.push(dataPoint)
      
      // Maintain buffer size if needed (optional optimization)
      const maxBufferSize = this.options.period * 10 // Keep 10x the period for smooth calculations
      if (this.rawDataBuffer.length > maxBufferSize) {
        this.rawDataBuffer = this.rawDataBuffer.slice(-maxBufferSize)
      }
      
      // Calculate new Bollinger Bands point if we have enough data
      if (this.rawDataBuffer.length >= this.options.period) {
        const newBBPoint = this.calculateSingleBollingerPoint(this.rawDataBuffer, this.rawDataBuffer.length - 1)
        debugger;
        if (newBBPoint && newBBPoint.upper && newBBPoint.lower) {
          // Add to our Bollinger Bands data
          this.upperBandData.push(newBBPoint.upper)
          this.lowerBandData.push(newBBPoint.lower)
          
          // Update both chart series with new Bollinger Bands points
          if (this.upperBandSeriesApi && this.lowerBandSeriesApi) {
            this.upperBandSeriesApi.update(newBBPoint.upper)
            this.lowerBandSeriesApi.update(newBBPoint.lower)
            console.log(`✅ BollingerBands ${this.seriesType} - Appended Bollinger Bands points`)
          }
        }
      } else {
        console.log(`⏳ BollingerBands ${this.seriesType} - Need ${this.options.period - this.rawDataBuffer.length} more points for Bollinger Bands`)
      }
    } catch (error) {
      console.error(`❌ BollingerBands ${this.seriesType} - Failed to append Bollinger Bands data:`, error)
      this.onError(`Bollinger Bands append failed: ${error}`)
    }
  }

  /**
   * BOLLINGER BANDS CALCULATION: Calculate Bollinger Bands for full dataset
   * Returns arrays of upper and lower band points starting from the period-th point
   */
  private calculateBollingerBands(data: Array<{ time: any, value: number }>): { 
    upperBand: Array<{ time: any, value: number }>, 
    lowerBand: Array<{ time: any, value: number }> 
  } {
    const upperBand: Array<{ time: any, value: number }> = []
    const lowerBand: Array<{ time: any, value: number }> = []

    // Calculate Bollinger Bands starting from the period-th point
    for (let i = this.options.period - 1; i < data.length; i++) {
      const bbPoint = this.calculateSingleBollingerPoint(data, i)
      if (bbPoint && bbPoint.upper && bbPoint.lower) {
        upperBand.push(bbPoint.upper)
        lowerBand.push(bbPoint.lower)
      }
    }
    
    console.log(`📊 BollingerBands ${this.seriesType} - Calculated ${upperBand.length} Bollinger Bands points from ${data.length} raw data points`)
    return { upperBand, lowerBand }
  }

  /**
   * BOLLINGER BANDS CALCULATION: Calculate single Bollinger Bands point at specific index
   * Returns upper and lower band values for the given index position
   */
  private calculateSingleBollingerPoint(data: Array<{ time: any, value: number }>, index: number): { 
    upper: { time: any, value: number } | null, 
    lower: { time: any, value: number } | null 
  } {
    if (index < this.options.period - 1 || index >= data.length) {
      return { upper: null, lower: null }
    }
    
    // Get the slice for this period
    const slice = data.slice(index - this.options.period + 1, index + 1)
    const values = slice.map(p => p.value)
    
    // Calculate moving average
    const mean = values.reduce((sum, val) => sum + val, 0) / values.length
    
    // Calculate standard deviation
    const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length
    const stdDev = Math.sqrt(variance)
    
    // Generate bands
    const upperValue = mean + (this.options.standardDeviations * stdDev)
    const lowerValue = mean - (this.options.standardDeviations * stdDev)
    
    return {
      upper: { time: data[index].time, value: upperValue },
      lower: { time: data[index].time, value: lowerValue }
    }
  }

  /**
   * CLEANUP: Override remove to clean up Bollinger Bands specific data
   * @override - because we have two seperate series we manage with bollinger bands, we need to remove it speeratly
   */
  remove(): void {
    console.log(`🧹 BollingerBands ${this.seriesType} - Cleaning up Bollinger Bands data`)
    
    // Remove both series from chart
    if (this.upperBandSeriesApi && this.chartInstance) {
      try {
        this.chartInstance.removeSeries(this.upperBandSeriesApi)
      } catch (error) {
        console.warn(`⚠️ BollingerBands ${this.seriesType} - Upper band series already removed:`, error)
      }
    }
    
    if (this.lowerBandSeriesApi && this.chartInstance) {
      try {
        this.chartInstance.removeSeries(this.lowerBandSeriesApi)
      } catch (error) {
        console.warn(`⚠️ BollingerBands ${this.seriesType} - Lower band series already removed:`, error)
      }
    }
    
    // Clear Bollinger Bands specific data
    this.rawDataBuffer = []
    this.upperBandData = []
    this.lowerBandData = []
    this.upperBandSeriesApi = null
    this.lowerBandSeriesApi = null
    
    // First remove from parent's children array
    if (this.parent) {
      this.parent.removeChild(this)
    }
    
    // Remove all children recursively
    [...this.children].forEach(child => child.remove())

    console.log(`✅ BollingerBands ${this.seriesType} - Bollinger Bands cleanup completed`)

    //unsubscribe
    this.unsubscribe()
  }
}

export default BollingerBands
