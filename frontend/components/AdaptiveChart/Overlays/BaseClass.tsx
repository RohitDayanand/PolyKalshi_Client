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
import { parseSubscriptionId } from '../utils/parseSubscriptionId'
import { generateSubscriptionId } from '@/lib/ChartStuff/subscription_baseline'

export default abstract class SeriesClass {
  // Core properties from your requirements
  protected seriesType: SeriesType  // 'YES' or 'NO'
  protected parent: SeriesClass | null
  protected children: SeriesClass[]
  protected chartInstance: IChartApi
  protected seriesApi: ISeriesApi<any> | null
  protected subscriptionId: string | null//Must be ssubscribed at any particular time
  private rxjsSubscription: Subscription | null = null
  private rxjsUnsubscribe: (() => void) | null = null  // Cleanup function for observable reuse
  private isSubscribed: boolean = false // Track subscription state
  private isRemoved: boolean = false // Track removal state to prevent double removal
  protected lastPoint: any = null // Store last point for time conflict detection
  
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
      } catch {
        // Series already removed or invalid
      } finally {
        this.seriesApi = null
      }
    }
    
    // Cleanup subscription
    this.unsubscribe()
  }

  // Subscription management - implemented in base class
  /*
  * 
  * This is subscription to the channel manager that ONLY happens on the 
  * creation of an instance, not on the set range of it
  * 
  */
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
    console.log(`🔍 [BASECLASS_SUBSCRIBE] ${this.seriesType} - Starting subscription attempt`, {
      marketId,
      side,
      timeRange,
      currentlySubscribed: this.isSubscribed,
      subscriptionId: this.subscriptionId,
      hasExistingRxjsSubscription: !!this.rxjsSubscription,
      hasExistingUnsubscribeFunction: !!this.rxjsUnsubscribe
    })

    if (this.isSubscribed) {
      console.log(`⚠️ [BASECLASS_SUBSCRIBE] ${this.seriesType} - Already subscribed, skipping`, {
        marketId,
        side,
        timeRange,
        currentSubscriptionId: this.subscriptionId
      })
      return
    }

    try {
      const attemptedChannel = `${marketId}&${side}&${timeRange}`
      console.log(`🚀 [BASECLASS_SUBSCRIBE] ${this.seriesType} - Creating RxJS channel subscription for: ${attemptedChannel}`)
      
      // Subscribe to the RxJS channel manager with cleanup tracking
      const { observable: channelObservable, unsubscribe } = rxjsChannelManager.subscribeWithCleanup(marketId, side, timeRange)
      
      console.log(`🔗 [BASECLASS_SUBSCRIBE] ${this.seriesType} - Got observable and unsubscribe function for: ${attemptedChannel}`)
      
      // Store cleanup function for proper reference counting
      this.rxjsUnsubscribe = unsubscribe
      
      this.rxjsSubscription = channelObservable.subscribe({
        next: (channelMessage: ChannelMessage) => {
          console.log(`📨 [BASECLASS_DATA] ${this.seriesType} - Received channel message`, {
            channel: channelMessage.channel,
            updateType: channelMessage.updateType,
            dataLength: Array.isArray(channelMessage.data) ? channelMessage.data.length : 1,
            hasSeriesApi: !!this.seriesApi,
            marketId,
            side,
            timeRange
          })

          if (!this.seriesApi) {
            console.warn(`⚠️ [BASECLASS_DATA] ${this.seriesType} - No seriesApi available, dropping message`, {
              channel: channelMessage.channel,
              updateType: channelMessage.updateType
            })
            return
          }

          try {
            if (channelMessage.updateType === 'initial_data') {
              // Handle initial data array with setData() for full dataset
              const initialData = channelMessage.data as DataPoint[]
              console.log(`📊 [BASECLASS_INITIAL_DATA] ${this.seriesType} - Processing initial data`, {
                channel: channelMessage.channel,
                dataPointCount: initialData.length,
                firstPoint: initialData[0] ? { time: initialData[0].time, value: initialData[0].value } : null,
                lastPoint: initialData[initialData.length - 1] ? { time: initialData[initialData.length - 1].time, value: initialData[initialData.length - 1].value } : null
              })
              
              // Convert DataPoint to chart format and use common updateData method. 
              // Default, we will just map the time and value, but subclasses can override the map
              // and retrieve the custom data that they want 
              
              const chartData = this.mapDataPointsToChartData(initialData)
              
              this.updateData(chartData)
              console.log(`✅ [BASECLASS_INITIAL_DATA] ${this.seriesType} - Successfully set initial data with ${chartData.length} points`)
              
            } else if (channelMessage.updateType === 'update') {
              // Handle single update with update() for performance  
              const updatePoint = channelMessage.data as DataPoint
              console.log(`🔄 [BASECLASS_UPDATE] ${this.seriesType} - Processing single update`, {
                channel: channelMessage.channel,
                time: updatePoint.time,
                value: updatePoint.value
              })
              
              // Use common appendData method
              this.appendData(this.mapUpdateToChartData(updatePoint))
              console.log(`✅ [BASECLASS_UPDATE] ${this.seriesType} - Successfully appended update point`)
            }
          } catch (error) {
            console.error(`❌ [BASECLASS_DATA_ERROR] ${this.seriesType} - Error processing RxJS channel data:`, {
              channel: channelMessage.channel,
              updateType: channelMessage.updateType,
              error: error,
              marketId,
              side,
              timeRange
            })
            this.onError(`RxJS channel data processing failed: ${error}`)
          }
        },
        error: (error) => {
          console.error(`❌ [BASECLASS_SUBSCRIPTION_ERROR] ${this.seriesType} - RxJS subscription error:`, {
            marketId,
            side,
            timeRange,
            channel: attemptedChannel,
            error: error
          })
          this.onError(`RxJS subscription failed: ${error}`)
        },
        complete: () => {
          console.log(`🏁 [BASECLASS_SUBSCRIPTION_COMPLETE] ${this.seriesType} - RxJS subscription completed`, {
            marketId,
            side,
            timeRange,
            channel: attemptedChannel
          })
        }
      })
      
      this.isSubscribed = true
      console.log(`✅ [BASECLASS_SUBSCRIBE_SUCCESS] ${this.seriesType} - Successfully subscribed to RxJS channel`, {
        marketId,
        side,
        timeRange,
        channel: attemptedChannel,
        subscriptionId: this.subscriptionId,
        hasRxjsSubscription: !!this.rxjsSubscription,
        hasUnsubscribeFunction: !!this.rxjsUnsubscribe
      })
      
    } catch (error) {
      console.error(`❌ [BASECLASS_SUBSCRIBE_ERROR] ${this.seriesType} - Failed to subscribe to RxJS channel:`, {
        marketId,
        side,
        timeRange,
        attemptedChannelAddress: `${marketId}&${side}&${timeRange}`,
        subscriptionId: this.subscriptionId,
        error: error,
        stack: error instanceof Error ? error.stack : 'No stack trace'
      })
      this.onError(`RxJS channel subscription failed: ${error}`)
    }
  }

  unsubscribe(): void {
    console.log(`🔌 [BASECLASS_UNSUBSCRIBE] ${this.seriesType} - Starting unsubscribe process`, {
      subscriptionId: this.subscriptionId,
      isSubscribed: this.isSubscribed,
      hasRxjsSubscription: !!this.rxjsSubscription,
      hasUnsubscribeFunction: !!this.rxjsUnsubscribe,
      marketId: this.marketId,
      currentTimeRange: this.currentTimeRange
    })

    try {
      if (this.subscriptionId && this.isSubscribed) {
        console.log(`🧹 [BASECLASS_UNSUBSCRIBE] ${this.seriesType} - Cleaning up subscriptions`, {
          subscriptionId: this.subscriptionId,
          marketId: this.marketId,
          timeRange: this.currentTimeRange
        })
        
        // Clean up RxJS subscription
        if (this.rxjsSubscription) {
          console.log(`🔗 [BASECLASS_UNSUBSCRIBE] ${this.seriesType} - Unsubscribing from RxJS observable`)
          this.rxjsSubscription.unsubscribe()
          this.rxjsSubscription = null
          console.log(`✅ [BASECLASS_UNSUBSCRIBE] ${this.seriesType} - RxJS subscription cleaned up`)
        }
        
        // Call cleanup function for reference counting
        if (this.rxjsUnsubscribe) {
          console.log(`📉 [BASECLASS_UNSUBSCRIBE] ${this.seriesType} - Calling reference counting cleanup function`)
          this.rxjsUnsubscribe()
          this.rxjsUnsubscribe = null
          console.log(`✅ [BASECLASS_UNSUBSCRIBE] ${this.seriesType} - Reference counting cleanup completed`)
        }
        
        this.isSubscribed = false
        
        // Call subclass-specific unsubscription hook
        console.log(`🎯 [BASECLASS_UNSUBSCRIBE] ${this.seriesType} - Calling onUnsubscribed hook`, {
          subscriptionId: this.subscriptionId
        })
        this.onUnsubscribed(this.subscriptionId)
        
        const oldSubscriptionId = this.subscriptionId
        this.subscriptionId = null
        
        console.log(`✅ [BASECLASS_UNSUBSCRIBE_SUCCESS] ${this.seriesType} - Successfully unsubscribed`, {
          oldSubscriptionId,
          marketId: this.marketId,
          timeRange: this.currentTimeRange,
          finalIsSubscribed: this.isSubscribed,
          finalSubscriptionId: this.subscriptionId
        })
      } else {
        console.log(`⚠️ [BASECLASS_UNSUBSCRIBE] ${this.seriesType} - Nothing to unsubscribe`, {
          subscriptionId: this.subscriptionId,
          isSubscribed: this.isSubscribed,
          reason: !this.subscriptionId ? 'No subscription ID' : 'Not subscribed'
        })
      }
    } catch (error) {
      console.error(`❌ [BASECLASS_UNSUBSCRIBE_ERROR] ${this.seriesType} - Unsubscription failed:`, {
        subscriptionId: this.subscriptionId,
        marketId: this.marketId,
        timeRange: this.currentTimeRange,
        error: error,
        stack: error instanceof Error ? error.stack : 'No stack trace'
      })
      this.onError(`Unsubscription failed: ${error}`)
    }
  }

  /**
  * Converts an array of DataPoint objects to the chart data format expected by lightweight-charts.
  * Subclasses can override this to provide custom mapping (e.g., OHLC, volume, etc).
  */

  protected mapDataPointsToChartData(dataPoints: DataPoint[]): any[] {
    // Default implementation: map to { time, value }
    return dataPoints.map(point => ({
      time: point.time as any,
      value: point.value
    }))
  }

  protected mapUpdateToChartData(dataPoint: DataPoint): any {
    return {
      time: dataPoint.time,
      value: dataPoint.value,
    }
  }

  // Common data update methods that work for all series types
  protected updateData(data: any[]): void {
    console.log(`📊 [BASECLASS_UPDATE_DATA] ${this.seriesType} - Updating chart data`, {
      dataLength: data.length,
      hasSeriesApi: !!this.seriesApi,
      subscriptionId: this.subscriptionId,
      marketId: this.marketId,
      timeRange: this.currentTimeRange,
      firstPoint: data[0] ? { time: data[0].time, value: data[0].value } : null,
      lastPoint: data[data.length - 1] ? { time: data[data.length - 1].time, value: data[data.length - 1].value } : null
    })
    
    if (this.seriesApi && data.length > 0) {
      try {
        this.seriesApi.setData(data)
        // Store the last point for time conflict detection
        this.lastPoint = data[data.length - 1]
        console.log(`✅ [BASECLASS_UPDATE_DATA_SUCCESS] ${this.seriesType} - Successfully set ${data.length} data points`)
      } catch (error) {
        console.error(`❌ [BASECLASS_UPDATE_DATA_ERROR] ${this.seriesType} - Data update failed:`, {
          dataLength: data.length,
          subscriptionId: this.subscriptionId,
          marketId: this.marketId,
          error: error
        })
        this.onError(`Data update failed: ${error}`)
      }
    } else {
      console.warn(`⚠️ [BASECLASS_UPDATE_DATA] ${this.seriesType} - Cannot update data`, {
        hasSeriesApi: !!this.seriesApi,
        dataLength: data.length,
        reason: !this.seriesApi ? 'No series API' : 'Empty data array'
      })
    }
  }

  protected appendData(dataPoint: any): void {
    console.log(`➕ [BASECLASS_APPEND_DATA] ${this.seriesType} - Appending single data point`, {
      dataPoint: { time: dataPoint.time, value: dataPoint.value },
      hasSeriesApi: !!this.seriesApi,
      subscriptionId: this.subscriptionId,
      marketId: this.marketId,
      timeRange: this.currentTimeRange,
      lastPoint: this.lastPoint
    })
    
    if (this.seriesApi) {
      try {
        this.seriesApi.update(dataPoint)
        // Store the successfully appended point as the new last point
        this.lastPoint = dataPoint
        console.log(`✅ [BASECLASS_APPEND_DATA_SUCCESS] ${this.seriesType} - Successfully appended data point`)
      } catch (error) {
        console.error(`❌ [BASECLASS_APPEND_DATA_ERROR] ${this.seriesType} - Data append failed:`, {
          dataPoint: { time: dataPoint.time, value: dataPoint.value },
          lastPoint: this.lastPoint,
          timeConflict: this.lastPoint && dataPoint.time <= this.lastPoint.time,
          subscriptionId: this.subscriptionId,
          marketId: this.marketId,
          error: error
        })
        
        // Check for time conflict specifically
        if (this.lastPoint && dataPoint.time <= this.lastPoint.time) {
          console.warn(`⚠️ [TIME_CONFLICT] ${this.seriesType} - Time conflict detected:`, {
            newPointTime: dataPoint.time,
            lastPointTime: this.lastPoint.time,
            newPointTimeType: typeof dataPoint.time,
            lastPointTimeType: typeof this.lastPoint.time,
            isRealConflict: dataPoint.time <= this.lastPoint.time
          })
        }
        
        this.onError(`Data append failed: ${error}`)
      }
    } else {
      console.warn(`⚠️ [BASECLASS_APPEND_DATA] ${this.seriesType} - Cannot append data, no series API available`, {
        dataPoint: { time: dataPoint.time, value: dataPoint.value },
        subscriptionId: this.subscriptionId,
        marketId: this.marketId
      })
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
  async setRange(newRange: TimeRange, marketId: string | null) {
    console.log(`🔄 [BASECLASS_RANGE_CHANGE] ${this.seriesType} - Starting range change`, {
      currentRange: this.currentTimeRange,
      newRange,
      currentSubscriptionId: this.subscriptionId,
      isCurrentlySubscribed: this.isSubscribed,
      instanceMarketId: this.marketId,
      parameterMarketId: marketId
    })

    // Use the instance's marketId if available, otherwise use the parameter
    const effectiveMarketId = this.marketId || marketId
    
    if (!effectiveMarketId) {
      console.warn(`⚠️ [BASECLASS_RANGE_CHANGE] ${this.seriesType} - No marketId available, aborting range change`, {
        newRange,
        currentRange: this.currentTimeRange,
        instanceMarketId: this.marketId,
        parameterMarketId: marketId
      })
      return
    }

    let newSubscriptionId: string
    try {
      newSubscriptionId = generateSubscriptionId(this.seriesType, newRange, effectiveMarketId)
    } catch (subscriptionError) {
      console.error(`❌ [BASECLASS_RANGE_CHANGE] ${this.seriesType} - Failed to generate subscription ID`, {
        newRange,
        currentRange: this.currentTimeRange,
        effectiveMarketId,
        error: subscriptionError
      })
      return
    }

    try {
      if (!newSubscriptionId) {
        console.warn(`⚠️ [BASECLASS_RANGE_CHANGE] ${this.seriesType} - No new subscription ID provided, aborting range change`, {
          newRange,
          currentRange: this.currentTimeRange
        })
        return
      }
      
      // If we're already subscribed to this range, do nothing
      if (this.subscriptionId === newSubscriptionId) {
        console.log(`ℹ️ [BASECLASS_RANGE_CHANGE] ${this.seriesType} - Already subscribed to target range, no change needed`, {
          subscriptionId: this.subscriptionId,
          newRange,
          currentRange: this.currentTimeRange
        })
        return
      }
      
      console.log(`🔌 [BASECLASS_RANGE_CHANGE] ${this.seriesType} - Unsubscribing from current range before switching`, {
        currentSubscriptionId: this.subscriptionId,
        currentRange: this.currentTimeRange,
        targetSubscriptionId: newSubscriptionId,
        targetRange: newRange
      })
      
      // Unsubscribe from current range
      if (this.subscriptionId && this.isSubscribed) {
        this.unsubscribe()
        console.log(`✅ [BASECLASS_RANGE_CHANGE] ${this.seriesType} - Successfully unsubscribed from old range`)
      }
      
      //Use utility function to 
      const newSubscription = parseSubscriptionId(newSubscriptionId)

      if (newSubscription) {
        const { marketId, side, timeRange } = newSubscription
        console.log(`📊 [BASECLASS_RANGE_CHANGE] ${this.seriesType} - Parsed subscription details`, {
          timeRange,
          marketId,
          side,
          previousMarketId: this.marketId,
          previousTimeRange: this.currentTimeRange
        })
        
        // Update our stored range BEFORE subscribing
        this.currentTimeRange = timeRange as TimeRange
        this.subscriptionId = newSubscriptionId as string
        
        console.log(`🚀 [BASECLASS_RANGE_CHANGE] ${this.seriesType} - Subscribing to new range`, {
          marketId,
          side,
          timeRange,
          newSubscriptionId
        })
        
        await this.subscribeToRxJSChannel(marketId, side, timeRange as any)
        
        console.log(`✅ [BASECLASS_RANGE_CHANGE] ${this.seriesType} - Successfully subscribed to new range`)
      } else {
        console.error(`❌ [BASECLASS_RANGE_CHANGE] ${this.seriesType} - Invalid subscription ID format`, {
          newSubscriptionId
        })
        return
      }
    
      // Update chart visible range
      const end_time: UTCTimestamp = toUtcTimestamp(this.chartInstance.timeScale().getVisibleRange()?.to) ?? (Date.now() / 1000 ) as UTCTimestamp;
      const newVisibleRange = {
        from: getVisibleRangeStart(end_time, newRange),
        to: end_time
      }
      
      console.log(`📈 [BASECLASS_RANGE_CHANGE] ${this.seriesType} - Updating chart visible range`, {
        newRange,
        end_time,
        newVisibleRange,
        marketId: this.marketId
      })
      
      this.chartInstance.timeScale().setVisibleRange(newVisibleRange)
      
      console.log(`🎉 [BASECLASS_RANGE_CHANGE_SUCCESS] ${this.seriesType} - Range change completed successfully`, {
        previousRange: 'unknown', // We updated this.currentTimeRange already
        newRange,
        newSubscriptionId,
        marketId: this.marketId,
        isSubscribed: this.isSubscribed
      })
      
    } catch (error) {
      console.error(`❌ [BASECLASS_RANGE_CHANGE_ERROR] ${this.seriesType} - Range switch failed:`, {
        currentRange: this.currentTimeRange,
        targetRange: newRange,
        currentSubscriptionId: this.subscriptionId,
        targetSubscriptionId: newSubscriptionId,
        marketId: this.marketId,
        error: error,
        stack: error instanceof Error ? error.stack : 'No stack trace'
      })
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