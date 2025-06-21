import { LineSeries as LightweightLineSeries, ISeriesApi, LineData, Time } from 'lightweight-charts'
import SeriesClass from './BaseClass'
import { SeriesClassConstructorOptions, MarketDataUpdate, MarketDataPoint } from '../../../lib/chart-types'
import { seriesOptions } from '../../../lib/chart-config'
import { marketDataEmitter } from '../../../lib/market-data-emitter'

export class LineSeries extends SeriesClass {
  private lineSeriesApi: ISeriesApi<'Line'> | null = null

  constructor(options: SeriesClassConstructorOptions) {
    super(options)
    try {
      this.seriesApi = this.createSeries()
      console.log(`✅ SeriesClass - Created ${this.seriesType} series with subscription ID: ${this.subscriptionId}`)
      
      // Auto-subscribe to market data if subscription ID exists
      // Note: Subclasses can override onSubscribed to handle their own subscription logic
      if (this.subscriptionId) {
        this.subscribe(this.subscriptionId)
      }
    } catch (error) {
      console.error(`❌ SeriesClass - Failed to create ${this.seriesType} series:`, error)
      this.onError(`Failed to create series: ${error}`)
    }

    //console.log(`📈 MovingAverage - Initialized ${this.seriesType} moving average with ${this.options.period}-point period`)

  }

  // Implementation of abstract createSeries method
  createSeries(): ISeriesApi<'Line'> {
    try {
      // Get series configuration based on type from chart-config
      const seriesConfig = this.seriesType === 'YES' ? seriesOptions.yes : seriesOptions.no
      
      // Create line series with configuration from chart-config
      this.lineSeriesApi = this.chartInstance.addSeries(LightweightLineSeries, {
        color: seriesConfig.color,
        priceLineColor: seriesConfig.priceLineColor,
        lineWidth: 2,
        priceLineVisible: true,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
      })

      console.log(`✅ LineSeries - Created ${this.seriesType} line series with color: ${seriesConfig.color}`)
      console.log(`🔗 LineSeries - Will be stored in BaseClass.seriesApi for market data handling`)
      
      return this.lineSeriesApi
    } catch (error) {
      console.error(`❌ LineSeries - Failed to create ${this.seriesType} line series:`, error)
      throw error
    }
  }

  // Getter for the typed line series API
  getLineSeriesApi(): ISeriesApi<'Line'> | null {
    return this.lineSeriesApi
  }
}

export default LineSeries 