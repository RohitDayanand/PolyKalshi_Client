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
import { SeriesType, SeriesClassConstructorOptions, MarketDataUpdate, MarketDataPoint } from '../../../lib/chart-types'
import { useMarketSubscriptionState } from '../hooks/useMarketSubscriptionState'
import { useChartRangeState } from '../hooks/useChartRangeState'
import { rxjsChannelManager } from '../../../lib/RxJSChannelManager'
import type { TimeRange, MarketSide, ChannelMessage, DataPoint } from '../../../lib/RxJSChannelManager'
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
  protected currentTimeRange: TimeRange = '1D'
  
  constructor(options: SeriesClassConstructorOptions) {
    this.seriesType = options.seriesType
    this.parent = options.parent || null
    this.children = []
    this.chartInstance = options.chartInstance
    this.seriesApi = null
    
    // Redux integration: Use provided subscription ID
    if (options.subscriptionId) {
      this.subscriptionId = options.subscriptionId
      console.log('📏 BaseClass - Using provided subscription ID:', this.subscriptionId)
    } else {
      // Subscription ID must be provided - cannot call hooks in constructor
      console.error('❌ BaseClass - No subscription ID provided. Hooks cannot be called in constructor.')
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
      console.log(`⏭️ BaseClass ${this.seriesType} - Already removed, skipping`)
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
        console.log(`✅ BaseClass ${this.seriesType} - Successfully removed series from chart`)
      } catch (error) {
        console.warn(`⚠️ BaseClass ${this.seriesType} - Series already removed or invalid:`, error)
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
      
      console.log(`✅ SeriesClass - Subscribed ${this.seriesType} to: ${marketId}&${side}&${timeRange}`)
      
      // Call subclass-specific subscription hook
      await this.onSubscribed(marketId)
    } catch (error) {
      console.error(`❌ SeriesClass - Failed to subscribe ${this.seriesType} to: ${marketId}`, error)
      this.onError(`Subscription failed: ${error}`)
    }
  }

  /**
   * Subscribe to RxJS channel manager using marketId&side&range format
   */
  private async subscribeToRxJSChannel(marketId: string, side: MarketSide, timeRange: TimeRange): Promise<void> {
    if (this.isSubscribed) {
      console.warn(`⚠️ ${this.seriesType} already subscribed to RxJS channel`)
      return
    }

    try {
      // Subscribe to the RxJS channel manager
      const channelObservable = rxjsChannelManager.subscribe(marketId, side, timeRange)
      
      this.rxjsSubscription = channelObservable.subscribe({
        next: (channelMessage: ChannelMessage) => {
          if (!this.seriesApi) {
            console.log(`⏭️ BaseClass ${this.seriesType} - Skipping event (no series API available)`)
            return
          }

          try {
            if (channelMessage.updateType === 'initial_data') {
              // Handle initial data array with setData() for full dataset
              const initialData = channelMessage.data as DataPoint[]
              console.log(`📊 BaseClass ${this.seriesType} - Received ${initialData.length} initial data points for ${channelMessage.channel}`)
              
              // Convert DataPoint to chart format and use common updateData method
              this.updateData(initialData.map(point => ({
                time: point.time as any,
                value: point.value
              })))
              console.log(`✅ BaseClass ${this.seriesType} - Loaded initial dataset successfully`)
              
            } else if (channelMessage.updateType === 'update') {
              // Handle single update with update() for performance  
              const updatePoint = channelMessage.data as DataPoint
              console.log(`📈 BaseClass ${this.seriesType} - Received real-time update:`, updatePoint)
              
              // Use common appendData method
              this.appendData({
                time: updatePoint.time as any,
                value: updatePoint.value
              })
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
      console.log(`✅ BaseClass ${this.seriesType} - Subscribed to RxJS channel: ${marketId}&${side}&${timeRange}`)
      
    } catch (error) {
      console.error(`❌ BaseClass ${this.seriesType} - Failed to subscribe to RxJS channel:`, error)
      this.onError(`RxJS channel subscription failed: ${error}`)
    }
  }

  unsubscribe(): void {
    try {
      if (this.subscriptionId && this.isSubscribed) {
        console.log(`🛑 BaseClass ${this.seriesType} - Unsubscribing from: ${this.subscriptionId}`)
        
        // Use the teardown function for proper cleanup
        if (this.unsubscribeFunction) {
          this.unsubscribeFunction()
          this.unsubscribeFunction = null
          console.log(`✅ BaseClass ${this.seriesType} - Teardown function executed`)
        }
        
        // Clean up event handler
        if (this.dataHandler) {
          marketDataEmitter.off('market-data', this.dataHandler)
          this.dataHandler = null
        }
        
        this.isSubscribed = false
        
        console.log(`✅ BaseClass ${this.seriesType} - Unsubscribed from: ${this.subscriptionId}`)
        
        // Call subclass-specific unsubscription hook
        this.onUnsubscribed(this.subscriptionId)
        
        this.subscriptionId = null
      }
    } catch (error) {
      console.error(`❌ BaseClass ${this.seriesType} - Failed to unsubscribe:`, error)
      this.onError(`Unsubscription failed: ${error}`)
    }
  }

  // Common data update methods that work for all series types
  protected updateData(data: any[]): void {
    if (this.seriesApi && data.length > 0) {
      try {
        this.seriesApi.setData(data)
        //console.log(`✅ BaseClass - Updated ${this.seriesType} with ${data.length} data points`)
      } catch (error) {
        console.error(`❌ BaseClass - Failed to update ${this.seriesType} data:`, error)
        this.onError(`Data update failed: ${error}`)
      }
    }
  }

  protected appendData(dataPoint: any): void {
    if (this.seriesApi) {
      try {
        this.seriesApi.update(dataPoint)
        //console.log(`✅ BaseClass - Appended data to ${this.seriesType}:`, dataPoint)
      } catch (error) {
        console.error(`❌ BaseClass - Failed to append data to ${this.seriesType}:`, error)
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
  async setRange(newRange: TimeRange, getNewSubscriptionId: (seriesType: SeriesType, range: string) => string): Promise<void> {
    try {
      console.log(`🔄 BaseClass ${this.seriesType} - Switching range to: ${newRange}`)
      
      // Get the new subscription ID for this series type and range
      const newSubscriptionId = getNewSubscriptionId(this.seriesType, newRange)
      
      if (!newSubscriptionId) {
        console.error(`❌ BaseClass ${this.seriesType} - No subscription ID found for range: ${newRange}`)
        return
      }
      
      // If we're already subscribed to this range, do nothing
      if (this.subscriptionId === newSubscriptionId) {
        console.log(`✅ BaseClass ${this.seriesType} - Already subscribed to range: ${newRange}`)
        return
      }
      
      // Unsubscribe from current range
      if (this.subscriptionId && this.isSubscribed) {
        console.log(`🛑 BaseClass ${this.seriesType} - Unsubscribing from current range: ${this.subscriptionId}`)
        this.unsubscribe()
      }
      
      // Subscribe to new range
      console.log(`🚀 BaseClass ${this.seriesType} - Subscribing to new range: ${newSubscriptionId}`)
      await this.subscribe(newSubscriptionId)
    
      //get endTime inside chart or now, should not make a different to be honest
      const end_time: UTCTimestamp = toUtcTimestamp(this.chartInstance.timeScale().getVisibleRange()?.to) ?? (Date.now() / 1000 ) as UTCTimestamp;
      
      this.chartInstance.timeScale().setVisibleRange({from: getVisibleRangeStart(end_time, newRange), to: end_time })

      console.log(`✅ BaseClass ${this.seriesType} - Successfully switched to range: ${newRange}`)
      
    } catch (error) {
      console.error(`❌ BaseClass ${this.seriesType} - Failed to switch range:`, error)
      this.onError(`Range switch failed: ${error}`)
    }
  }
  
  // Abstract method for creating the actual chart series - to be implemented by subclasses
  abstract createSeries(): ISeriesApi<any>

  // Error handling with console logging as per requirement #5
  protected onError(error: string): void {
    console.error(`❌ SeriesClass Error [${this.seriesType}]:`, error)
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