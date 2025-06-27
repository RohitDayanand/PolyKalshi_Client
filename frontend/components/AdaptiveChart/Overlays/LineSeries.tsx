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
      console.log(`✅ SeriesClass - Created ${this.seriesType} series with subscription ID: ${this.subscriptionId}`)
      
      // Auto-subscribe to market data if subscription ID exists
      // Parse subscription ID to extract marketId, side, and timeRange
      if (this.subscriptionId) {
        console.log(`🔗 LineSeries - Attempting subscription with ID: ${this.subscriptionId}`)
        
        // Parse subscription ID format: "marketId&side&timeRange" (RxJS format)
        const subscriptionParts = this.subscriptionId.split('&')
        if (subscriptionParts.length >= 3) {
          const [marketId, sideStr, timeRange] = subscriptionParts
          // Ensure side is lowercase to match RxJS MarketSide type
          const side = sideStr.toLowerCase() as 'yes' | 'no'
          
          console.log(`🔍 [SUBSCRIPTION_ATTEMPT] LineSeries parsing subscription ID:`, {
            originalSubscriptionId: this.subscriptionId,
            parsedMarketId: marketId,
            parsedSide: side,
            parsedTimeRange: timeRange,
            seriesType: this.seriesType,
            conversionFromSeriesType: `${this.seriesType} -> ${side}`
          })
          
          console.log(`🔍 [SUBSCRIPTION_ATTEMPT] LineSeries attempting to subscribe with:`, {
            marketId,
            side,
            timeRange,
            targetChannelKey: `${marketId}&${side}&${timeRange}`
          })
          
          this.subscribe(marketId, side, timeRange as any)
        } else {
          console.error(`🔍 [SUBSCRIPTION_ERROR] LineSeries - Invalid subscription ID format:`, {
            subscriptionId: this.subscriptionId,
            expectedFormat: 'marketId&side&timeRange',
            actualParts: subscriptionParts,
            partCount: subscriptionParts.length
          })
        }
      } else {
        console.warn(`⚠️ LineSeries - No subscription ID provided for ${this.seriesType} series`)
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