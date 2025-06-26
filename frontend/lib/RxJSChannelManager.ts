import { Subject, BehaviorSubject, Observable, Subscription, interval } from 'rxjs'
import { filter, map, throttleTime, distinctUntilChanged, switchMap, catchError } from 'rxjs/operators'
import { TIME_RANGES, TimeRange as ChartTimeRange } from './ChartStuff/chart-types'
import { LRUCache } from 'lru-cache'
import { of } from 'rxjs'

export type TimeRange = ChartTimeRange // Use canonical TimeRange from chart-types
export type MarketSide = 'yes' | 'no'
export type UpdateType = 'initial_data' | 'update'

export interface DataPoint {
  time: number
  value: number
  volume?: number
}

export interface TickerData {
  type: 'ticker_update'
  market_id: string
  platform: 'polymarket' | 'kalshi'
  summary_stats: {
    yes?: { bid: number; ask: number; volume: number }
    no?: { bid: number; ask: number; volume: number }
  }
  timestamp: number
}

export interface ChannelMessage {
  channel: string
  updateType: UpdateType
  data: DataPoint | DataPoint[]
}

interface ChannelConfig {
  marketId: string
  side: MarketSide
  range: TimeRange
  platform: 'polymarket' | 'kalshi'
  cache: DataPoint[] // Legacy array cache, will be replaced by LRU
  lruCache: LRUCache<number, DataPoint> // New LRU cache keyed by timestamp
  lastEmitTime: number
  throttleMs: number
  lastApiPoll: number
  apiPollInterval: number // milliseconds between API polls
  isPolling: boolean
}

export class RxJSChannelManager {
  private channelSubject = new Subject<ChannelMessage>()
  private websocketConnected = new BehaviorSubject<boolean>(false)
  private channels = new Map<string, ChannelConfig>()
  private websocket: WebSocket | null = null
  private maxCacheSize: number = 300
  private defaultThrottleMs: number = 1000
  private apiPollIntervals = new Map<string, NodeJS.Timeout>()
  private defaultApiPollInterval: number = 60000 // 1 minute

  constructor(maxCacheSize: number = 300, defaultThrottleMs: number = 1000) {
    this.maxCacheSize = maxCacheSize
    this.defaultThrottleMs = defaultThrottleMs
  }

  /**
   * Generate channel key in format: market_id&side&range
   */
  private generateChannelKey(marketId: string, side: MarketSide, range: TimeRange): string {
    return `${marketId}&${side}&${range}`
  }

  /**
   * Parse channel key back to components
   */
  private parseChannelKey(channelKey: string): { marketId: string; side: MarketSide; range: TimeRange } | null {
    const parts = channelKey.split('&')
    if (parts.length !== 3) {
      console.log(`🔍 [CHANNEL_PARSE_ERROR] Invalid channel key format: ${channelKey} - expected 3 parts, got ${parts.length}`)
      return null
    }
    
    const [marketId, side, range] = parts
    
    // Use canonical TIME_RANGES from chart-types.ts
    const validSides = ['yes', 'no']
    const validRanges = TIME_RANGES // Now uses ['1H', '1W', '1M', '1Y'] from chart-types.ts
    
    console.log(`🔍 [CHANNEL_PARSE_TRACE] Parsing channel key: ${channelKey}`, {
      parts,
      marketId,
      side,
      range,
      validSides,
      validRanges,
      sideValid: validSides.includes(side),
      rangeValid: validRanges.includes(range as TimeRange)
    })
    
    if (!validSides.includes(side) || !validRanges.includes(range as TimeRange)) {
      console.log(`🔍 [CHANNEL_PARSE_ERROR] Invalid side or range in: ${channelKey}`, {
        side,
        range,
        sideValid: validSides.includes(side),
        rangeValid: validRanges.includes(range as TimeRange)
      })
      return null
    }
    
    const result = {
      marketId,
      side: side as MarketSide,
      range: range as TimeRange
    }
    
    console.log(`✅ [CHANNEL_PARSE_SUCCESS] Successfully parsed: ${channelKey}`, result)
    return result
  }

  /**
   * Set WebSocket instance from existing singleton
   */
  setWebSocketInstance(ws: WebSocket | null) {
    
    if (this.websocket) {
      this.websocket.removeEventListener('message', this.handleWebSocketMessage)
    }

    this.websocket = ws
    
    if (this.websocket) {
      this.websocket.addEventListener('message', this.handleWebSocketMessage)
      this.websocketConnected.next(true)
    } else {
      this.websocketConnected.next(false)
    }
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleWebSocketMessage = (event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data)
      
      if (message.type === 'ticker_update') {
        this.processTickerUpdate(message as TickerData)
      }
    } catch (error) {
    }
  }

  /**
   * Process incoming ticker updates and route to appropriate channels
   */
  private processTickerUpdate(tickerData: TickerData) {
    const marketId = tickerData.market_id
    

    // Process both sides
    this.processSideUpdate(marketId, 'yes', tickerData)
    this.processSideUpdate(marketId, 'no', tickerData)
  }

  /**
   * Process ticker update for a specific side (yes/no)
   */
  private processSideUpdate(marketId: string, side: MarketSide, tickerData: TickerData) {
    const sideData = tickerData.summary_stats[side]
    if (!sideData) return

    // Calculate midpoint price
    const midpoint = sideData.bid !== null && sideData.ask !== null 
      ? (sideData.bid + sideData.ask) / 2 
      : 0.5

    const dataPoint: DataPoint = {
      time: Math.floor(tickerData.timestamp),
      value: Math.max(0, Math.min(1, midpoint)),
      volume: sideData.volume
    }

    // Emit to all canonical time ranges for this side
    for (const range of TIME_RANGES) { // Use canonical ['1H', '1W', '1M', '1Y'] from chart-types.ts
      const channelKey = this.generateChannelKey(marketId, side, range)
      const channelConfig = this.channels.get(channelKey)
      
      console.log(`🔍 [EMISSION_ATTEMPT] Attempting to emit to channel:`, {
        marketId,
        side,
        range,
        channelKey,
        channelExists: !!channelConfig,
        dataPoint: { time: dataPoint.time, value: dataPoint.value, volume: dataPoint.volume }
      })
      
      if (channelConfig) {
        this.emitToChannel(channelKey, channelConfig, dataPoint)
        console.log(`✅ [EMISSION_SUCCESS] Data emitted to channel: ${channelKey}`)
      } else {
        console.warn(`🚨 [EMISSION_FAILED] Channel does not exist: ${channelKey} - no subscribers yet?`)
      }
    }
  }

  /**
   * Emit data point to specific channel with throttling
   */
  private emitToChannel(channelKey: string, channelConfig: ChannelConfig, dataPoint: DataPoint) {
    const now = Date.now()
    
    // Add to cache
    channelConfig.cache.push(dataPoint)
    if (channelConfig.cache.length > this.maxCacheSize) {
      channelConfig.cache.shift()
    }

    // Check throttling
    if (now - channelConfig.lastEmitTime < channelConfig.throttleMs) {
      console.log(`🔍 [EMISSION_THROTTLED] Channel ${channelKey} throttled (${now - channelConfig.lastEmitTime}ms < ${channelConfig.throttleMs}ms)`)
      return
    }

    channelConfig.lastEmitTime = now
    
    const message: ChannelMessage = {
      channel: channelKey,
      updateType: 'update',
      data: dataPoint
    }
    
    console.log(`📡 [DATA_EMITTED] RxJS message sent to subscribers:`, {
      channel: channelKey,
      updateType: message.updateType,
      dataPoint: { time: dataPoint.time, value: dataPoint.value },
      cacheSize: channelConfig.cache.length,
      timeSinceLastEmit: now - (channelConfig.lastEmitTime - channelConfig.throttleMs)
    })
    
    this.channelSubject.next(message)
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
    const channelKey = this.generateChannelKey(marketId, side, range)
    
    // TRACE: Log the actual emitter connection details
    console.log(`🔍 [EMITTER_ADDRESS_TRACE] RxJSChannelManager.subscribe() called:`, {
      requestedMarketId: marketId,
      requestedSide: side,
      requestedRange: range,
      generatedChannelKey: channelKey,
      channelExists: this.channels.has(channelKey),
      totalChannels: this.channels.size,
      websocketConnected: this.websocketConnected.value
    })
    
    // Create channel config if it doesn't exist
    if (!this.channels.has(channelKey)) {
      const channelConfig: ChannelConfig = {
        marketId,
        side,
        range,
        platform: 'polymarket', // Default, will be set properly in onMarketSubscribed
        cache: [],
        lruCache: new LRUCache<number, DataPoint>({
          max: this.maxCacheSize,
          ttl: 1000 * 60 * 60 // 1 hour TTL
        }),
        lastEmitTime: 0,
        throttleMs: throttleMs || this.defaultThrottleMs,
        lastApiPoll: 0,
        apiPollInterval: this.defaultApiPollInterval,
        isPolling: false
      }
      
      this.channels.set(channelKey, channelConfig)
      console.warn(`🚨 [EMITTER_CREATION_WARNING] NEW CHANNEL CREATED - This should be rare!`, {
        channelKey,
        marketId,
        side,
        range,
        throttleMs: channelConfig.throttleMs,
        totalChannelsNow: this.channels.size,
        reason: 'Channel did not exist when subscription was attempted'
      })
      console.log(`🔍 [EMITTER_CHANNEL_CREATED] RxJSChannelManager created new channel:`, {
        channelKey,
        marketId,
        side,
        range,
        throttleMs: channelConfig.throttleMs
      })
      
      // Fetch historical data
      this.fetchAndReplayHistory(channelKey, channelConfig)
    } else if (throttleMs !== undefined) {
      // Update throttling if provided
      this.channels.get(channelKey)!.throttleMs = throttleMs
    }


    console.log(`🔍 [EMITTER_OBSERVABLE_RETURN] RxJSChannelManager returning observable for channel: ${channelKey}`)
    
    // Immediately emit cached data if available
    const channelConfig = this.channels.get(channelKey)
    if (channelConfig && channelConfig.lruCache.size > 0) {
      const cachedData = this.getChannelLRUCache(channelConfig.marketId, channelConfig.side, channelConfig.range)
      if (cachedData.length > 0) {
        console.log(`📡 [IMMEDIATE_CACHE_EMIT] Emitting ${cachedData.length} cached points to new ${channelKey} subscriber`)
        
        // Emit cached data asynchronously to not block subscription
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
      this.generateChannelKey(marketId, side, range)
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
   * Get observable for WebSocket connection status
   */
  getConnectionStatus(): Observable<boolean> {
    return this.websocketConnected.asObservable()
  }

  /**
   * Manually replay historical data for a channel
   */
  replay(marketId: string, side: MarketSide, range: TimeRange): void {
    const channelKey = this.generateChannelKey(marketId, side, range)
    const channelConfig = this.channels.get(channelKey)
    
    if (!channelConfig) {
      return
    }

    if (channelConfig.cache.length > 0) {
      const message: ChannelMessage = {
        channel: channelKey,
        updateType: 'initial_data',
        data: [...channelConfig.cache]
      }
      
      this.channelSubject.next(message)
    }
  }

  /**
   * Fetch historical data and replay to channel using LRU cache
   */
  private async fetchAndReplayHistory(channelKey: string, channelConfig: ChannelConfig) {
    try {
      console.log(`🔄 [API_POLL] Fetching history for ${channelKey}`, {
        marketId: channelConfig.marketId,
        platform: channelConfig.platform,
        side: channelConfig.side,
        range: channelConfig.range
      })
      
      // Build API URL with channel-specific parameters
      const historyUrl = `/api/history/${channelConfig.platform}/${channelConfig.marketId}?side=${channelConfig.side}&range=${channelConfig.range}&limit=${this.maxCacheSize}`
      
      const response = await fetch(historyUrl)
      if (!response.ok) {
        throw new Error(`API request failed: ${response.status} ${response.statusText}`)
      }
      
      const historyData: DataPoint[] = await response.json()
      
      if (historyData.length > 0) {
        console.log(`✅ [API_POLL] Received ${historyData.length} historical points for ${channelKey}`)
        
        // Store in both caches (LRU is primary, array is legacy)
        historyData.forEach(point => {
          channelConfig.lruCache.set(point.time, point)
        })
        channelConfig.cache = [...historyData]
        
        // Update last poll time
        channelConfig.lastApiPoll = Date.now()
        
        // Emit to channel subscribers
        const message: ChannelMessage = {
          channel: channelKey,
          updateType: 'initial_data',
          data: historyData
        }
        
        this.channelSubject.next(message)
        console.log(`📡 [INITIAL_DATA_EMITTED] Sent ${historyData.length} points to ${channelKey} subscribers`)
        
        // Start periodic polling for this channel
        this.startChannelPolling(channelKey, channelConfig)
      } else {
        console.log(`📭 [API_POLL] No historical data available for ${channelKey}`)
        // Still start polling even if no initial data
        this.startChannelPolling(channelKey, channelConfig)
      }
      
    } catch (error) {
      console.error(`❌ [API_POLL] Failed to fetch history for ${channelKey}:`, error)
      // Start polling anyway to retry
      this.startChannelPolling(channelKey, channelConfig)
    }
  }

  /**
   * Start periodic polling for a channel
   */
  private startChannelPolling(channelKey: string, channelConfig: ChannelConfig) {
    if (channelConfig.isPolling) {
      console.log(`⚠️ [POLLING] Channel ${channelKey} already polling, skipping`)
      return
    }

    channelConfig.isPolling = true
    
    const pollInterval = setInterval(async () => {
      await this.pollChannelData(channelKey, channelConfig)
    }, channelConfig.apiPollInterval)
    
    this.apiPollIntervals.set(channelKey, pollInterval)
    console.log(`🔄 [POLLING_STARTED] Polling every ${channelConfig.apiPollInterval}ms for ${channelKey}`)
  }

  /**
   * Poll for new data for a specific channel
   */
  private async pollChannelData(channelKey: string, channelConfig: ChannelConfig) {
    try {
      const lastDataTime = channelConfig.lruCache.size > 0 
        ? Math.max(...Array.from(channelConfig.lruCache.keys()))
        : 0

      const historyUrl = `/api/history/${channelConfig.platform}/${channelConfig.marketId}?side=${channelConfig.side}&range=${channelConfig.range}&since=${lastDataTime}&limit=100`
      
      const response = await fetch(historyUrl)
      if (!response.ok) {
        throw new Error(`Poll request failed: ${response.status}`)
      }
      
      const newData: DataPoint[] = await response.json()
      
      if (newData.length > 0) {
        console.log(`🔄 [POLL_UPDATE] Received ${newData.length} new points for ${channelKey}`)
        
        // Add to LRU cache and legacy array
        newData.forEach(point => {
          if (!channelConfig.lruCache.has(point.time)) {
            channelConfig.lruCache.set(point.time, point)
            channelConfig.cache.push(point)
          }
        })
        
        // Trim legacy array to max size
        if (channelConfig.cache.length > this.maxCacheSize) {
          channelConfig.cache = channelConfig.cache.slice(-this.maxCacheSize)
        }
        
        // Emit individual updates
        newData.forEach(point => {
          const message: ChannelMessage = {
            channel: channelKey,
            updateType: 'update',
            data: point
          }
          this.channelSubject.next(message)
        })
        
        channelConfig.lastApiPoll = Date.now()
      }
      
    } catch (error) {
      console.error(`❌ [POLL_ERROR] Failed to poll ${channelKey}:`, error)
    }
  }

  /**
   * Get current cache for a channel
   */
  getChannelCache(marketId: string, side: MarketSide, range: TimeRange): DataPoint[] {
    const channelKey = this.generateChannelKey(marketId, side, range)
    const channelConfig = this.channels.get(channelKey)
    return channelConfig ? [...channelConfig.cache] : []
  }

  /**
   * Get statistics about the manager
   */
  getStats() {
    const stats = {
      totalChannels: this.channels.size,
      activeChannels: this.channels.size,
      totalCacheSize: 0,
      websocketConnected: this.websocketConnected.value,
      channels: [] as any[]
    }

    for (const [channelKey, config] of this.channels.entries()) {
      stats.totalCacheSize += config.cache.length
      
      stats.channels.push({
        channelKey,
        marketId: config.marketId,
        side: config.side,
        range: config.range,
        cacheSize: config.cache.length,
        throttleMs: config.throttleMs,
        lastEmitTime: config.lastEmitTime
      })
    }

    return stats
  }

  /**
   * Called by Redux middleware when a market gets marked as subscribed
   * Creates all channel combinations for the market (yes/no × 1D/1W/1M)
   */
  onMarketSubscribed(marketId: string, platform: 'polymarket' | 'kalshi') {
    
    // Create channels for all combinations of sides and ranges
    const sides: MarketSide[] = ['yes', 'no']
    const ranges: TimeRange[] = ['1H', '1W', '1M', '1Y']
    
    let channelsCreated = 0
    
    for (const side of sides) {
      for (const range of ranges) {
        const channelKey = this.generateChannelKey(marketId, side, range)
        
        // Create channel config if it doesn't exist
        if (!this.channels.has(channelKey)) {
          const channelConfig: ChannelConfig = {
            marketId,
            side,
            range,
            platform,
            cache: [],
            lruCache: new LRUCache<number, DataPoint>({
              max: this.maxCacheSize,
              ttl: 1000 * 60 * 60 // 1 hour TTL
            }),
            lastEmitTime: 0,
            throttleMs: this.defaultThrottleMs,
            lastApiPoll: 0,
            apiPollInterval: this.defaultApiPollInterval,
            isPolling: false
          }
          
          this.channels.set(channelKey, channelConfig)
          channelsCreated++
          
          // Fetch historical data for this channel
          this.fetchAndReplayHistory(channelKey, channelConfig)
        } else {
        }
      }
    }
    
  }

  /**
   * Get LRU cache data for a channel
   */
  getChannelLRUCache(marketId: string, side: MarketSide, range: TimeRange): DataPoint[] {
    const channelKey = this.generateChannelKey(marketId, side, range)
    const channelConfig = this.channels.get(channelKey)
    if (!channelConfig) return []
    
    // Convert LRU cache to sorted array
    const cacheEntries = Array.from(channelConfig.lruCache.entries())
    return cacheEntries
      .sort(([a], [b]) => a - b) // Sort by timestamp
      .map(([_, dataPoint]) => dataPoint)
  }

  /**
   * Stop polling for a specific channel
   */
  stopChannelPolling(channelKey: string) {
    const interval = this.apiPollIntervals.get(channelKey)
    if (interval) {
      clearInterval(interval)
      this.apiPollIntervals.delete(channelKey)
      
      const channelConfig = this.channels.get(channelKey)
      if (channelConfig) {
        channelConfig.isPolling = false
      }
      
      console.log(`🛑 [POLLING_STOPPED] Stopped polling for ${channelKey}`)
    }
  }

  /**
   * Clean up resources
   */
  destroy() {
    console.log('🧹 [CLEANUP] Destroying RxJSChannelManager...')
    
    // Stop all polling intervals
    for (const [channelKey, interval] of this.apiPollIntervals.entries()) {
      clearInterval(interval)
      console.log(`🛑 [CLEANUP] Stopped polling for ${channelKey}`)
    }
    this.apiPollIntervals.clear()
    
    // Clean up WebSocket
    if (this.websocket) {
      this.websocket.removeEventListener('message', this.handleWebSocketMessage)
    }
    
    // Complete observables
    this.channelSubject.complete()
    this.websocketConnected.complete()
    
    // Clear all channels (this will also clear LRU caches)
    this.channels.clear()
    
    console.log('✅ [CLEANUP] RxJSChannelManager destroyed')
  }
}

// Export singleton instance
export const rxjsChannelManager = new RxJSChannelManager()