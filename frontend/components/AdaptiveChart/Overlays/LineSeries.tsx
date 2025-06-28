import { LineSeries as LightweightLineSeries, ISeriesApi, LineData, Time } from 'lightweight-charts'
import SeriesClass from './BaseClass'
import { SeriesClassConstructorOptions, MarketDataUpdate, MarketDataPoint } from '../../../lib/ChartStuff/chart-types'
import { seriesOptions } from '../../../lib/ChartStuff/chart-config'
// import { marketDataEmitter } from '../../../lib/market-data-emitter' // No longer needed with RxJS channel manager

export class LineSeries extends SeriesClass {
  private lineSeriesApi: ISeriesApi<'Line'> | null = null

  constructor(options: SeriesClassConstructorOptions) {
    super(options)
    try {
      this.seriesApi = this.createSeries()
      
      // Auto-subscribe to market data if subscription ID exists
      // Parse subscription ID to extract marketId, side, and timeRange
      if (this.subscriptionId) {
        
        // Parse subscription ID format: "marketId&side&timeRange" (RxJS format)
        const subscriptionParts = this.subscriptionId.split('&')
        if (subscriptionParts.length >= 3) {
          const [marketId, sideStr, timeRange] = subscriptionParts
          // Ensure side is lowercase to match RxJS MarketSide type
          const side = sideStr.toLowerCase() as 'yes' | 'no'
          
          
          
          this.subscribe(marketId, side, timeRange as any)
        } else {
          // Invalid subscription ID format
        }
      } else {
        // No subscription ID provided
      }
    } catch (error) {
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

      
      return this.lineSeriesApi
    } catch (error) {
      throw error
    }
  }

  // Getter for the typed line series API
  getLineSeriesApi(): ISeriesApi<'Line'> | null {
    return this.lineSeriesApi
  }
}

export default LineSeries 