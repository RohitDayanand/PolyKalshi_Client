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
import { marketDataEmitter } from '../../../lib/market-data-emitter'
import type { TimeRange } from '../../../lib/chart-types'
import { getVisibleRangeStart, toUtcTimestamp } from '../../../lib/time-horizontalscale'

export default abstract class SeriesClass {
  // Core properties from your requirements
  protected seriesType: SeriesType  // 'YES' or 'NO'
  protected parent: SeriesClass | null
  protected children: SeriesClass[]
  protected chartInstance: IChartApi
  protected seriesApi: ISeriesApi<any> | null
  protected subscriptionId: string | null
  private dataHandler: ((data: MarketDataUpdate) => void) | null = null
  private unsubscribeFunction: (() => void) | null = null // Store teardown function
  private isSubscribed: boolean = false // Track subscription state
  private isRemoved: boolean = false // Track removal state to prevent double removal
  
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
  async subscribe(subscriptionId: string): Promise<void> {
    try {
      this.subscriptionId = subscriptionId
      
      // Check if subclass has overridden onSubscribed with custom logic
      const hasCustomSubscription = this.onSubscribed !== SeriesClass.prototype.onSubscribed
      
      if (!hasCustomSubscription) {
        // Use base class market data handling for default implementation
        await this.subscribeToMarketData(subscriptionId)
      }
      
      console.log(`✅ SeriesClass - Subscribed ${this.seriesType} to: ${subscriptionId}`)
      
      // Call subclass-specific subscription hook
      await this.onSubscribed(subscriptionId)
    } catch (error) {
      console.error(`❌ SeriesClass - Failed to subscribe ${this.seriesType} to: ${subscriptionId}`, error)
      this.onError(`Subscription failed: ${error}`)
    }
  }

  /**
   * PURE BROADCAST: Common market data subscription using pure event filtering
   * Uses teardown function pattern for proper cleanup
   */
  private async subscribeToMarketData(subscriptionId: string): Promise<void> {
    if (this.isSubscribed) {
      console.warn(`⚠️ ${this.seriesType} already subscribed to market data`)
      return
    }

    // Set up event listener that filters by subscription ID
    const dataHandler = (updateData: MarketDataUpdate) => {
      // Only process data for our subscription ID
      if (updateData.subscriptionId !== subscriptionId) {
        return // Skip events for other subscriptions
      }
      
      if (!this.seriesApi) {
        console.log(`⏭️ BaseClass ${this.seriesType} - Skipping event (no series API available)`)
        return
      }

      try {
        if (updateData.type === 'initial') {
          // Handle initial data array with setData() for full dataset
          const initialData = updateData.data as MarketDataPoint[]
          console.log(`📊 BaseClass ${this.seriesType} - Received ${initialData.length} initial data points for ${subscriptionId}`)
          
          // Use common updateData method
          this.updateData(initialData.map(point => ({
            time: point.time as any,
            value: point.value
          })))
          console.log(`✅ BaseClass ${this.seriesType} - Loaded initial dataset successfully`)
          
        } else if (updateData.type === 'update') {
          // Handle single update with update() for performance  
          const updatePoint = updateData.data as MarketDataPoint
          console.log(`📈 BaseClass ${this.seriesType} - Received real-time update:`, updatePoint)
          
          // Use common appendData method
          this.appendData({
            time: updatePoint.time as any,
            value: updatePoint.value
          })
          
        }
      } catch (error) {
        console.error(`❌ BaseClass ${this.seriesType} - Error processing market data:`, error)
        this.onError(`Market data processing failed: ${error}`)
      }
    }

    // Store the handler for cleanup
    this.dataHandler = dataHandler

    // Subscribe to global market data events (pure broadcast)
    marketDataEmitter.on('market-data', dataHandler)
    
    // Subscribe to the market data feed to start receiving data
    // This returns a teardown function for proper cleanup
    try {
      const subscriptionConfig = {
        id: subscriptionId,
        updateFrequency: 1000, // 1 second updates
        historyLimit: 1000     // Keep 1000 points in cache
      }
      
      console.log(`🚀 BaseClass ${this.seriesType} - Starting market data subscription:`, subscriptionConfig)
      
      // Store the teardown function for proper cleanup
      this.unsubscribeFunction = marketDataEmitter.subscribe(subscriptionConfig)
      this.isSubscribed = true
      
      console.log(`✅ BaseClass ${this.seriesType} - Market data subscription started for ${subscriptionId}`)
      
    } catch (error) {
      console.error(`❌ BaseClass ${this.seriesType} - Failed to subscribe to market data emitter:`, error)
      this.onError(`Market data emitter subscription failed: ${error}`)
    }
    
    console.log(`🔗 BaseClass ${this.seriesType} - Subscribed to market data: ${subscriptionId}`)
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