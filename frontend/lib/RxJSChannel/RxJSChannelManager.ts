import { Subject, BehaviorSubject, Observable } from 'rxjs'
import { filter, distinctUntilChanged } from 'rxjs/operators'
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
    
    console.log(`🔍 [CHANNEL_MANAGER] Subscribe called for ${channelKey}`, {
      marketId, side, range,
      channelExists: this.channels.has(channelKey),
      totalChannels: this.channels.size
    })
    
    // Create channel if it doesn't exist
    if (!this.channels.has(channelKey)) {
      this.createChannel(marketId, side, range, 'polymarket', throttleMs)
    } else if (throttleMs !== undefined) {
      // Update throttling if provided
      this.channels.get(channelKey)!.throttleMs = throttleMs
    }

    // Emit cached data immediately if available
    this.emitCachedDataIfAvailable(channelKey)
    
    // Return filtered observable for this channel
    return this.channelSubject.pipe(
      filter(message => message.channel === channelKey),
      distinctUntilChanged((prev, curr) => 
        JSON.stringify(prev.data) === JSON.stringify(curr.data)
      )
    )
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
    console.log("I have an obvious error, yet I am being called ?")
    
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
    
    const channelConfig: ChannelConfig = {
      marketId,
      side,
      range,
      platform,
      cache: [],
      lruCache: this.channelCache.createLRUCache(),
      lastEmitTime: 0,
      throttleMs: throttleMs || this.defaultThrottleMs,
      lastApiPoll: 0,
      apiPollInterval: this.defaultApiPollInterval,
      isPolling: false
    }
    
    this.channels.set(channelKey, channelConfig)
    
    console.log(`✅ [CHANNEL_MANAGER] Created channel: ${channelKey}`, {
      platform, throttleMs: channelConfig.throttleMs
    })
    
    // Fetch initial data using ApiPoller
    this.apiPoller.fetchInitialData(channelKey, channelConfig)
  }

  /**
   * Emit cached data immediately if available for new subscribers
   */
  private emitCachedDataIfAvailable(channelKey: string): void {
    const channelConfig = this.channels.get(channelKey)
    if (!channelConfig || !this.channelCache.hasData(channelConfig)) {
      return
    }

    const cachedData = this.channelCache.getCachedData(channelConfig)
    if (cachedData.length > 0) {
      console.log(`📡 [IMMEDIATE_CACHE_EMIT] Emitting ${cachedData.length} cached points to new ${channelKey} subscriber`)
      
      // Emit cached data asynchronously
      setTimeout(() => {
        const message: ChannelMessage = {
          channel: channelKey,
          updateType: 'initial_data',
          data: cachedData
        }
        this.channelSubject.next(message)
      }, 0)
    }
  }

  /**
   * Manually replay historical data for a channel
   */
  replay(marketId: string, side: MarketSide, range: TimeRange): void {
    const channelKey = ChannelCache.generateChannelKey(marketId, side, range)
    const channelConfig = this.channels.get(channelKey)
    
    if (!channelConfig) {
      console.warn(`[CHANNEL_MANAGER] Cannot replay: channel ${channelKey} not found`)
      return
    }

    const cachedData = this.channelCache.getCachedData(channelConfig)
    if (cachedData.length > 0) {
      const message: ChannelMessage = {
        channel: channelKey,
        updateType: 'initial_data',
        data: cachedData
      }
      
      this.channelSubject.next(message)
      console.log(`🔄 [CHANNEL_MANAGER] Replayed ${cachedData.length} points for ${channelKey}`)
    }
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
      stats.totalCacheSize += cacheStats.arrayCacheSize
      
      const channelStats: ChannelStats = {
        channelKey,
        marketId: config.marketId,
        side: config.side,
        range: config.range,
        platform: config.platform,
        cacheSize: cacheStats.arrayCacheSize,
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