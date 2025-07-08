import { Subject, BehaviorSubject, Observable } from 'rxjs'
import { filter, distinctUntilChanged, shareReplay } from 'rxjs/operators'
import { TIME_RANGES } from '../ChartStuff/chart-types'
import { 
  TimeRange, 
  MarketSide, 
  Platform, 
  DataPoint, 
  ChannelMessage, 
  ChannelConfig, 
  ManagerStats,
  ChannelStats
} from './types'
import { ChannelCache } from './ChannelCache'
import { ApiPoller } from './ApiPoller'
import { WebSocketHandler } from './WebSocketHandler'
import {defer, of, merge} from 'rxjs'

/**
 * Main RxJS Channel Manager - orchestrates all channel operations
 * Uses composition pattern with specialized subclasses
 */
export class RxJSChannelManager {
  // Core observables
  private channelSubject = new Subject<ChannelMessage>()
  private websocketConnected = new BehaviorSubject<boolean>(false)
  
  // Channel storage
  private channels = new Map<string, ChannelConfig>()
  
  // Configuration
  private maxCacheSize: number
  private defaultThrottleMs: number
  private defaultApiPollInterval: number = 600000 // 10 minute

  // Specialized handlers
  private channelCache: ChannelCache
  private apiPoller: ApiPoller
  private webSocketHandler: WebSocketHandler

  constructor(maxCacheSize: number = 300, defaultThrottleMs: number = 1000) {
    this.maxCacheSize = maxCacheSize
    this.defaultThrottleMs = defaultThrottleMs

    // Initialize specialized handlers
    this.channelCache = new ChannelCache(maxCacheSize)
    this.apiPoller = new ApiPoller(
      this.channelSubject, 
      this.channelCache, 
      this.defaultApiPollInterval, 
      maxCacheSize
    )
    this.webSocketHandler = new WebSocketHandler(
      this.websocketConnected,
      this.channelSubject,
      this.channels,
      this.channelCache
    )
  }

  /**
   * Set WebSocket instance (delegates to WebSocketHandler)
   */
  setWebSocketInstance(ws: WebSocket | null): void {
    this.webSocketHandler.setWebSocketInstance(ws)
  }

  /**
   * Subscribe to a specific channel
   */
  subscribe(
    marketId: string, 
    side: MarketSide, 
    range: TimeRange, 
    throttleMs?: number
  ): Observable<ChannelMessage> {
    const channelKey = ChannelCache.generateChannelKey(marketId, side, range)
    
    console.log(`🔍 [CHANNEL_MANAGER_SUBSCRIBE] Subscribe called for ${channelKey}`, {
      marketId, 
      side, 
      range,
      channelExists: this.channels.has(channelKey),
      totalChannels: this.channels.size,
      allChannelKeys: Array.from(this.channels.keys()),
      requestedThrottleMs: throttleMs
    })
    
    // Create channel if it doesn't exist
    // @TODO @ERROR - edit because we currently do not support Polymarket subscriptions 
    if (!this.channels.has(channelKey)) {
      console.log(`🆕 [CHANNEL_MANAGER_SUBSCRIBE] Channel doesn't exist, creating new channel: ${channelKey}`)
      this.createChannel(marketId, side, range, 'polymarket', throttleMs)
    } else if (throttleMs !== undefined) {
      // Update throttling if provided
      const oldThrottleMs = this.channels.get(channelKey)!.throttleMs
      this.channels.get(channelKey)!.throttleMs = throttleMs
      console.log(`⚙️ [CHANNEL_MANAGER_SUBSCRIBE] Updated throttling for ${channelKey}: ${oldThrottleMs}ms -> ${throttleMs}ms`)
    }

    //Typechecker - we know this should not be null otherwise we have some serious prolems 
    const channelConfig = this.channels.get(channelKey)!
    const cacheSize = this.channelCache.getCachedData(channelConfig).length
    
    console.log(`📊 [CHANNEL_MANAGER_SUBSCRIBE] Channel config details for ${channelKey}`, {
      platform: channelConfig.platform,
      throttleMs: channelConfig.throttleMs,
      lastEmitTime: channelConfig.lastEmitTime,
      lastApiPoll: channelConfig.lastApiPoll,
      isPolling: channelConfig.isPolling,
      subscriberCount: channelConfig.subscriberCount,
      hasSharedObservable: !!channelConfig.sharedObservable,
      cacheSize
    })
    
    // Create shared observable if it doesn't exist
    if (!channelConfig.sharedObservable) {
      console.log(`🆕 [CHANNEL_MANAGER_OBSERVABLE] Creating new shared observable for ${channelKey}`, {
        cacheSize,
        hasLruCache: !!channelConfig.lruCache,
        currentSubscriberCount: channelConfig.subscriberCount
      })
      channelConfig.sharedObservable = this.createSharedObservable(channelKey)
      
      // Emit cached data once when observable is first created
      console.log(`📡 [CHANNEL_MANAGER_OBSERVABLE] Attempting to emit cached data for new observable: ${channelKey}`)
    } else {
      console.log(`♻️ [CHANNEL_MANAGER_OBSERVABLE] Reusing existing shared observable for ${channelKey}`, {
        cacheSize,
        currentSubscriberCount: channelConfig.subscriberCount,
        willEmitCachedData: cacheSize > 0
      })
    }
    
    // Increment reference count
    channelConfig.subscriberCount++
    console.log(`📈 [CHANNEL_MANAGER_SUBSCRIBE] ${channelKey} subscriber count increased to: ${channelConfig.subscriberCount}`, {
      totalChannels: this.channels.size,
      cacheSize
    })
    
    // Return the hydrated initial obserable
    return this.getHydratedObservable(channelKey)
  }

  /**
   * Subscribe with proper cleanup tracking for reference counting
   */
  subscribeWithCleanup(
    marketId: string, 
    side: MarketSide, 
    range: TimeRange, 
    throttleMs?: number
  ): { observable: Observable<ChannelMessage>, unsubscribe: () => void } {
    const channelKey = ChannelCache.generateChannelKey(marketId, side, range)
    
    console.log(`🔗 [CHANNEL_MANAGER_CLEANUP] Creating subscription with cleanup for ${channelKey}`, {
      marketId,
      side,
      range,
      throttleMs
    })
    
    const observable = this.subscribe(marketId, side, range, throttleMs)
    
    const channelConfig = this.channels.get(channelKey)
    const initialCacheSize = channelConfig ? this.channelCache.getCachedData(channelConfig).length : 0
    
    console.log(`✅ [CHANNEL_MANAGER_CLEANUP] Created subscription with cleanup for ${channelKey}`, {
      initialSubscriberCount: channelConfig?.subscriberCount || 0,
      initialCacheSize,
      hasSharedObservable: !!channelConfig?.sharedObservable
    })
    
    const unsubscribe = () => {
      console.log(`🔌 [CHANNEL_MANAGER_UNSUBSCRIBE] Starting unsubscribe for ${channelKey}`, {
        marketId,
        side,
        range
      })
      
      const channelConfig = this.channels.get(channelKey)
      if (channelConfig) {
        const beforeCount = channelConfig.subscriberCount
        const cacheSize = this.channelCache.getCachedData(channelConfig).length
        
        // Decrement reference count
        channelConfig.subscriberCount = Math.max(0, channelConfig.subscriberCount - 1)
        
        console.log(`📉 [CHANNEL_MANAGER_UNSUBSCRIBE] ${channelKey} subscriber count decreased`, {
          before: beforeCount,
          after: channelConfig.subscriberCount,
          cacheSize,
          hasSharedObservable: !!channelConfig.sharedObservable
        })
        
        // Clean up shared observable if no more subscribers
        // Note: shareReplay with refCount: true should handle this automatically,
        // but we can also explicitly clean up here for extra safety
        if (channelConfig.subscriberCount === 0) {
          console.log(`🧹 [CHANNEL_MANAGER_CLEANUP] No more subscribers for ${channelKey}, cleaning up shared observable`, {
            finalCacheSize: cacheSize,
            hadSharedObservable: !!channelConfig.sharedObservable,
            totalChannels: this.channels.size
          })
          
          // Clear the shared observable but keep the channel config and cache
          channelConfig.sharedObservable = undefined
          
          console.log(`✅ [CHANNEL_MANAGER_CLEANUP] Cleaned up shared observable for ${channelKey}, cache preserved`)
        } else {
          console.log(`📊 [CHANNEL_MANAGER_UNSUBSCRIBE] ${channelKey} still has ${channelConfig.subscriberCount} subscribers, keeping shared observable`)
        }
      } else {
        console.warn(`⚠️ [CHANNEL_MANAGER_UNSUBSCRIBE] Channel config not found for ${channelKey} during unsubscribe`)
      }
    }
    
    return { observable, unsubscribe }
  }

  /**
   * Subscribe to multiple channels at once
   */
  subscribeToChannels(channels: Array<{marketId: string, side: MarketSide, range: TimeRange}>): Observable<ChannelMessage> {
    const channelKeys = channels.map(({marketId, side, range}) => 
      ChannelCache.generateChannelKey(marketId, side, range)
    )
    
    // Ensure all channels exist
    channels.forEach(({marketId, side, range}) => {
      this.subscribe(marketId, side, range)
    })
    
    return this.channelSubject.pipe(
      filter(message => channelKeys.includes(message.channel))
    )
  }

  /**
   * Called by Redux middleware when a market gets subscribed
   * Creates all channel combinations for the market
   */
  onMarketSubscribed(marketId: string, platform: Platform): void {
    console.log(`🎯 [CHANNEL_MANAGER] Market subscribed: ${marketId} on ${platform}`)
    
    const sides: MarketSide[] = ['yes', 'no']
    const ranges: TimeRange[] = [...TIME_RANGES]
    
    let channelsCreated = 0
    
    for (const side of sides) {
      for (const range of ranges) {
        const channelKey = ChannelCache.generateChannelKey(marketId, side, range)
        
        if (!this.channels.has(channelKey)) {
          this.createChannel(marketId, side, range, platform)
          channelsCreated++
        }
      }
    }
    
    console.log(`✅ [CHANNEL_MANAGER] Created ${channelsCreated} channels for market ${marketId}`)
  }

  /**
   * Create a new channel with all required configuration
   */
  private createChannel(
    marketId: string, 
    side: MarketSide, 
    range: TimeRange, 
    platform: Platform,
    throttleMs?: number
  ): void {
    const channelKey = ChannelCache.generateChannelKey(marketId, side, range)
    
    console.log(`🔧 [CHANNEL_MANAGER_CREATE] Creating new channel: ${channelKey}`, {
      marketId,
      side,
      range,
      platform,
      requestedThrottleMs: throttleMs,
      defaultThrottleMs: this.defaultThrottleMs,
      totalChannelsBefore: this.channels.size
    })
    
    const lruCache = this.channelCache.createLRUCache()
    
    const channelConfig: ChannelConfig = {
      marketId,
      side,
      range,
      platform,
      lruCache,
      lastEmitTime: 0,
      throttleMs: throttleMs || this.defaultThrottleMs,
      lastApiPoll: 0,
      apiPollInterval: this.defaultApiPollInterval,
      isPolling: false,
      // Observable reuse fields
      sharedObservable: undefined,
      subscriberCount: 0
    }
    
    this.channels.set(channelKey, channelConfig)
    
    console.log(`✅ [CHANNEL_MANAGER_CREATE] Successfully created channel: ${channelKey}`, {
      platform, 
      finalThrottleMs: channelConfig.throttleMs,
      apiPollInterval: channelConfig.apiPollInterval,
      totalChannelsAfter: this.channels.size,
      hasLruCache: !!channelConfig.lruCache,
      maxCacheSize: this.maxCacheSize
    })
    
    // Fetch initial data using ApiPoller
    console.log(`📥 [CHANNEL_MANAGER_CREATE] Initiating initial data fetch for: ${channelKey}`)
    this.apiPoller.fetchInitialData(channelKey, channelConfig)
  }

  /**
   * Create a shared observable with automatic cleanup for a specific channel
   */
  private createSharedObservable(channelKey: string): Observable<ChannelMessage> {
    const channelConfig = this.channels.get(channelKey)
    const cacheSize = channelConfig ? this.channelCache.getCachedData(channelConfig).length : 0
    
    console.log(`🔄 [CHANNEL_MANAGER_OBSERVABLE_CREATE] Creating shared observable for ${channelKey}`, {
      channelExists: !!channelConfig,
      cacheSize,
      subscriberCount: channelConfig?.subscriberCount || 0,
      platform: channelConfig?.platform,
      throttleMs: channelConfig?.throttleMs
    })
    
    const sharedObservable = this.channelSubject.pipe(
      filter(message => {
        const matches = message.channel === channelKey
        if (matches) {
          console.log(`📨 [CHANNEL_MANAGER_FILTER] Message passed filter for ${channelKey}`, {
            updateType: message.updateType,
            dataLength: Array.isArray(message.data) ? message.data.length : 1
          })
        }
        return matches
      }),
      distinctUntilChanged((prev, curr) => {
        const isDuplicate = JSON.stringify(prev.data) === JSON.stringify(curr.data)
        if (isDuplicate) {
          console.log(`🔄 [CHANNEL_MANAGER_DEDUPE] Filtered out duplicate message for ${channelKey}`, {
            updateType: curr.updateType
          })
        }
        return isDuplicate
      }),
      shareReplay({
        refCount: true, 
        bufferSize: 0})
    )
    
    console.log(`✅ [CHANNEL_MANAGER_OBSERVABLE_CREATE] Created shared observable for ${channelKey}`, {
      cacheSize,
      willAutoCleanup: true
    })
    
    return sharedObservable
  }

  /*
  * Gets historical price
  */
  private getHydratedObservable(channelKey: string): Observable<ChannelMessage> {
    const channelConfig = this.channels.get(channelKey)
    if (!channelConfig) {
      throw new Error(`[CHANNEL_MANAGER] Channel ${channelKey} not found`)
    }

    // Ensure we have one shared live stream
    if (!channelConfig.sharedObservable) {
      channelConfig.sharedObservable = this.createSharedObservable(channelKey)
    }
    const live$ = channelConfig.sharedObservable

    // 🔑  defer guarantees the snapshot lookup happens for *every* subscriber
    return defer(() => {
      const snapshot = this.channelCache.getCachedData(channelConfig)

      // No history yet?  Just hand back the live stream.
      if (snapshot.length === 0) {
        return live$
      }

      const initialMsg: ChannelMessage = {
        channel: channelKey,
        updateType: 'initial_data',
        data: snapshot
      }

      // Emit snapshot first, then live updates
      //First emits initial message
      return merge(of(initialMsg), live$)
    })
  }


  /**
   * Get WebSocket connection status
   */
  getConnectionStatus(): Observable<boolean> {
    return this.webSocketHandler.getConnectionStatus()
  }

  /**
   * Get LRU cache data for a channel
   */
  getChannelLRUCache(marketId: string, side: MarketSide, range: TimeRange): DataPoint[] {
    const channelKey = ChannelCache.generateChannelKey(marketId, side, range)
    const channelConfig = this.channels.get(channelKey)
    return channelConfig ? this.channelCache.getCachedData(channelConfig) : []
  }

  /**
   * Stop polling for a specific channel
   */
  stopChannelPolling(channelKey: string): void {
    const channelConfig = this.channels.get(channelKey)
    this.apiPoller.stopPolling(channelKey, channelConfig)
  }

  /**
   * Get comprehensive statistics about the manager
   */
  getStats(): ManagerStats {
    const stats: ManagerStats = {
      totalChannels: this.channels.size,
      activeChannels: this.channels.size,
      totalCacheSize: 0,
      websocketConnected: this.webSocketHandler.isConnected(),
      channels: []
    }

    for (const [channelKey, config] of this.channels.entries()) {
      const cacheStats = this.channelCache.getCacheStats(config)
      stats.totalCacheSize += cacheStats.lruCacheSize
      
      const channelStats: ChannelStats = {
        channelKey,
        marketId: config.marketId,
        side: config.side,
        range: config.range,
        platform: config.platform,
        cacheSize: cacheStats.lruCacheSize,
        lruCacheSize: cacheStats.lruCacheSize,
        throttleMs: config.throttleMs,
        lastEmitTime: config.lastEmitTime,
        lastApiPoll: config.lastApiPoll,
        isPolling: config.isPolling
      }
      
      stats.channels.push(channelStats)
    }

    return stats
  }

  /**
   * Clean up all resources
   */
  destroy(): void {
    console.log('🧹 [CHANNEL_MANAGER] Destroying RxJSChannelManager...')
    
    // Stop all polling
    this.apiPoller.destroy()
    
    // Clean up WebSocket
    this.webSocketHandler.destroy()
    
    // Complete observables
    this.channelSubject.complete()
    this.websocketConnected.complete()
    
    // Clear all channels
    this.channels.clear()
    
    console.log('✅ [CHANNEL_MANAGER] RxJSChannelManager destroyed')
  }

  
}


// Export singleton instance
export const rxjsChannelManager = new RxJSChannelManager()