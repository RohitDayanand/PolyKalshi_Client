/*
 * Use lightweight-cimport { IChartApi, ISeriesApi } from 'lightweight-charts'
import { SeriesType, SeriesClassConstructorOptions } from '../../../lib/chart-types'
import { useMarketSubscriptionState } from '../hooks/useMarketSubscriptionState'


export default abstract class SeriesClass { to define overlays ontop of price series and build a superclass
 that defines core features. We will follow a dependency manager system design pattern



 *Core functions
 *  store yes/no
 *  store parent class ref - i.e the series owned
 *  store children in a SeriesClass array
 *  remove function that first calls parent.removeChild(this) to remove it from its own array, then removes
 *  the overlay using chart.removeSeries()
 *  subscribe function (yes/no) --> subscribe to the global market id yes/no emitter, runs async to update
 *   
 *  
 *  in the constructor --> let individual series override, but core things are parent ref, yes/no, children array  
 *  which some of which should be passed in as arguments 
 * 
 * 

 
 
 */

import { IChartApi, ISeriesApi, UTCTimestamp } from 'lightweight-charts'
import { SeriesType, SeriesClassConstructorOptions, MarketDataUpdate, MarketDataPoint, TimeRange } from '../../../lib/ChartStuff/chart-types'
import { useMarketSubscriptionState } from '../hooks/useMarketSubscriptionState'
import { useChartRangeState } from '../hooks/useChartRangeState'
import { rxjsChannelManager } from '../../../lib/RxJSChannel'
import type { MarketSide, ChannelMessage, DataPoint } from '../../../lib/RxJSChannel'
import { getVisibleRangeStart, toUtcTimestamp } from '../../../lib/time-horizontalscale'
import { Subscription } from 'rxjs'

export default abstract class SeriesClass {
  // Core properties from your requirements
  protected seriesType: SeriesType  // 'YES' or 'NO'
  protected parent: SeriesClass | null
  protected children: SeriesClass[]
  protected chartInstance: IChartApi
  protected seriesApi: ISeriesApi<any> | null
  protected subscriptionId: string | null
  private rxjsSubscription: Subscription | null = null
  private isSubscribed: boolean = false // Track subscription state
  private isRemoved: boolean = false // Track removal state to prevent double removal
  
  // New properties for RxJS channel manager
  protected marketId: string | null = null
  protected currentTimeRange: TimeRange = '1H'
  
  constructor(options: SeriesClassConstructorOptions) {
    this.seriesType = options.seriesType
    this.parent = options.parent || null
    this.children = []
    this.chartInstance = options.chartInstance
    this.seriesApi = null
    
    // Redux integration: Use provided subscription ID
    if (options.subscriptionId) {
      this.subscriptionId = options.subscriptionId
    } else {
      // Subscription ID must be provided - cannot call hooks in constructor
      this.subscriptionId = `fallback_${this.seriesType}_${Date.now()}`
    }
    
    // Add this instance to parent's children if parent exists
    if (this.parent) {
      this.parent.addChild(this)
    }
    
    //Create series will be implemented in the individual constructor
  }

  // Core dependency management functions
  addChild(child: SeriesClass): void {
    if (!this.children.includes(child)) {
      this.children.push(child)
    }
  }

  removeChild(child: SeriesClass): void {
    const index = this.children.indexOf(child)
    if (index > -1) {
      this.children.splice(index, 1)
    }
  }

  // Remove function following your specification
  remove(): void {
    // Prevent double removal
    if (this.isRemoved) {
      return
    }
    
    // Mark as removed immediately
    this.isRemoved = true
    
    // First remove from parent's children array
    if (this.parent) {
      this.parent.removeChild(this)
    }
    
    // Remove all children recursively
    [...this.children].forEach(child => child.remove())
    
    // Remove the actual chart series with error handling
    if (this.seriesApi && this.chartInstance) {
      try {
        this.chartInstance.removeSeries(this.seriesApi)
      } catch (error) {
        // Series already removed or invalid
      } finally {
        this.seriesApi = null
      }
    }
    
    // Cleanup subscription
    this.unsubscribe()
  }

  // Subscription management - implemented in base class
  async subscribe(marketId: string, side: MarketSide, timeRange: TimeRange): Promise<void> {
    try {
      this.marketId = marketId
      this.currentTimeRange = timeRange
      
      // Check if subclass has overridden onSubscribed with custom logic
      const hasCustomSubscription = this.onSubscribed !== SeriesClass.prototype.onSubscribed
      
      if (!hasCustomSubscription) {
        // Use base class market data handling for default implementation
        await this.subscribeToRxJSChannel(marketId, side, timeRange)
      }
      
      // Call subclass-specific subscription hook
      await this.onSubscribed(marketId)
    } catch (error) {
      this.onError(`Subscription failed: ${error}`)
    }
  }

  /**
   * Subscribe to RxJS channel manager using marketId&side&range format
   */
  private async subscribeToRxJSChannel(marketId: string, side: MarketSide, timeRange: TimeRange): Promise<void> {
    if (this.isSubscribed) {
      return
    }

    try {
      // TRACE: Log the subscription attempt with all details
      const attemptedChannel = `${marketId}&${side}&${timeRange}`
      
      // Subscribe to the RxJS channel manager
      const channelObservable = rxjsChannelManager.subscribe(marketId, side, timeRange)
      
      this.rxjsSubscription = channelObservable.subscribe({
        next: (channelMessage: ChannelMessage) => {
          if (!this.seriesApi) {
            return
          }

          try {

            if (channelMessage.updateType === 'initial_data') {
              // Handle initial data array with setData() for full dataset
              const initialData = channelMessage.data as DataPoint[]
              
              // Convert DataPoint to chart format and use common updateData method
              const chartData = initialData.map(point => ({
                time: point.time as any,
                value: point.value
              }))
              
              this.updateData(chartData)
              
            } else if (channelMessage.updateType === 'update') {
              // Handle single update with update() for performance  
              const updatePoint = channelMessage.data as DataPoint
              
              // Use common appendData method
              const chartPoint = {
                time: updatePoint.time as any,
                value: updatePoint.value
              }
              this.appendData(chartPoint)
            }
          } catch (error) {
            console.error(`❌ BaseClass ${this.seriesType} - Error processing RxJS channel data:`, error)
            this.onError(`RxJS channel data processing failed: ${error}`)
          }
        },
        error: (error) => {
          console.error(`❌ BaseClass ${this.seriesType} - RxJS subscription error:`, error)
          this.onError(`RxJS subscription failed: ${error}`)
        }
      })
      
      this.isSubscribed = true
      console.log(`🔍 [EMITTER_CONNECTION_SUCCESS] BaseClass ${this.seriesType} - Successfully connected to RxJS channel: ${marketId}&${side}&${timeRange}`)
      console.log(`✅ BaseClass ${this.seriesType} - Subscribed to RxJS channel: ${marketId}&${side}&${timeRange}`)
      
    } catch (error) {
      console.error(`🔍 [EMITTER_CONNECTION_FAILED] BaseClass ${this.seriesType} - Failed to subscribe to RxJS channel:`, {
        marketId,
        side,
        timeRange,
        attemptedChannelAddress: `${marketId}&${side}&${timeRange}`,
        error: error
      })
      this.onError(`RxJS channel subscription failed: ${error}`)
    }
  }

  unsubscribe(): void {
    try {
      if (this.subscriptionId && this.isSubscribed) {
        
        // Clean up RxJS subscription
        if (this.rxjsSubscription) {
          this.rxjsSubscription.unsubscribe()
          this.rxjsSubscription = null
        }
        
        this.isSubscribed = false
        
        // Call subclass-specific unsubscription hook
        this.onUnsubscribed(this.subscriptionId)
        
        this.subscriptionId = null
      }
    } catch (error) {
      this.onError(`Unsubscription failed: ${error}`)
    }
  }

  // Common data update methods that work for all series types
  protected updateData(data: any[]): void {
    
    if (this.seriesApi && data.length > 0) {
      try {
        this.seriesApi.setData(data)
      } catch (error) {
        this.onError(`Data update failed: ${error}`)
      }
    }
  }

  protected appendData(dataPoint: any): void {
    
    if (this.seriesApi) {
      try {
        this.seriesApi.update(dataPoint)
      } catch (error) {
        this.onError(`Data append failed: ${error}`)
      }
    }
    //this.chartInstance.timeScale().fitContent()
  }

  // Optional hooks for subclasses to override if they need custom subscription behavior
  protected async onSubscribed(subscriptionId: string): Promise<void> {
    // Default implementation does nothing - subclasses can override
  }

  protected onUnsubscribed(subscriptionId: string): void {
    // Default implementation does nothing - subclasses can override
  }

  /**
   * NEW: Range switching functionality
   * Switches the series to a new time range by changing subscription
   */
  async setRange(newRange: TimeRange, newSubscriptionId: String | null) {
    try {
      
      
      if (!newSubscriptionId) {
        return
      }
      
      // If we're already subscribed to this range, do nothing
      if (this.subscriptionId === newSubscriptionId) {
        return
      }
      
      // Unsubscribe from current range
      if (this.subscriptionId && this.isSubscribed) {
        this.unsubscribe()
      }
      
      // Subscribe to new range
      
      // Parse the new subscription ID to get marketId, side, timeRange
      // Expected format: seriesType&timeRange&marketId (using & as delimiter to avoid conflicts)
      const subscriptionParts = newSubscriptionId.split('&')
      if (subscriptionParts.length >= 3) {
        const [seriesTypeStr, timeRange, ...marketIdParts] = subscriptionParts
        const marketId = marketIdParts.join('&') // Rejoin in case marketId contains &
        const side = seriesTypeStr.toLowerCase() as 'yes' | 'no'
        await this.subscribe(marketId, side, timeRange as any)
      } else {
        return
      }
    
      //get endTime inside chart or now, should not make a different to be honest
      const end_time: UTCTimestamp = toUtcTimestamp(this.chartInstance.timeScale().getVisibleRange()?.to) ?? (Date.now() / 1000 ) as UTCTimestamp;
      
      this.chartInstance.timeScale().setVisibleRange({from: getVisibleRangeStart(end_time, newRange), to: end_time })
      
    } catch (error) {
      this.onError(`Range switch failed: ${error}`)
    }
  }
  
  // Abstract method for creating the actual chart series - to be implemented by subclasses
  abstract createSeries(): ISeriesApi<any>

  // Error handling
  protected onError(error: string): void {
    // Subclasses can override this for custom error handling
  }

  // Getters
  getSeriesType(): SeriesType {
    return this.seriesType
  }

  getParent(): SeriesClass | null {
    return this.parent
  }

  getChildren(): SeriesClass[] {
    return [...this.children] // Return copy to prevent external modification
  }

  getSeriesApi(): ISeriesApi<any> | null {
    return this.seriesApi
  }

  getSubscriptionId(): string | null {
    return this.subscriptionId
  }
}