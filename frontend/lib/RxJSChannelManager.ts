import { Subject, BehaviorSubject, Observable, Subscription } from 'rxjs'
import { filter, map, throttleTime, distinctUntilChanged } from 'rxjs/operators'

export type TimeRange = '1D' | '1W' | '1M'
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
  cache: DataPoint[]
  lastEmitTime: number
  throttleMs: number
}

export class RxJSChannelManager {
  private channelSubject = new Subject<ChannelMessage>()
  private websocketConnected = new BehaviorSubject<boolean>(false)
  private channels = new Map<string, ChannelConfig>()
  private websocket: WebSocket | null = null
  private maxCacheSize: number = 300
  private defaultThrottleMs: number = 1000

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
    if (parts.length !== 3) return null
    
    const [marketId, side, range] = parts
    if (!['yes', 'no'].includes(side) || !['1D', '1W', '1M'].includes(range)) {
      return null
    }
    
    return {
      marketId,
      side: side as MarketSide,
      range: range as TimeRange
    }
  }

  /**
   * Set WebSocket instance from existing singleton
   */
  setWebSocketInstance(ws: WebSocket | null) {
    console.log('📡 RxJSChannelManager: Setting WebSocket instance')
    
    if (this.websocket) {
      this.websocket.removeEventListener('message', this.handleWebSocketMessage)
    }

    this.websocket = ws
    
    if (this.websocket) {
      this.websocket.addEventListener('message', this.handleWebSocketMessage)
      this.websocketConnected.next(true)
      console.log('✅ RxJSChannelManager: WebSocket listener attached')
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
      console.error('❌ RxJSChannelManager: Error processing WebSocket message:', error)
    }
  }

  /**
   * Process incoming ticker updates and route to appropriate channels
   */
  private processTickerUpdate(tickerData: TickerData) {
    const marketId = tickerData.market_id
    
    console.log(`📊 RxJSChannelManager: Processing ticker for ${marketId}`)

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

    // Emit to all time ranges for this side
    for (const range of ['1D', '1W', '1M'] as TimeRange[]) {
      const channelKey = this.generateChannelKey(marketId, side, range)
      const channelConfig = this.channels.get(channelKey)
      
      if (channelConfig) {
        this.emitToChannel(channelKey, channelConfig, dataPoint)
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
      console.log(`⏱️ RxJSChannelManager: Throttling emission for ${channelKey}`)
      return
    }

    channelConfig.lastEmitTime = now
    
    const message: ChannelMessage = {
      channel: channelKey,
      updateType: 'update',
      data: dataPoint
    }
    
    this.channelSubject.next(message)
    console.log(`📤 RxJSChannelManager: Emitted update for ${channelKey}`)
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
    
    // Create channel config if it doesn't exist
    if (!this.channels.has(channelKey)) {
      const channelConfig: ChannelConfig = {
        marketId,
        side,
        range,
        cache: [],
        lastEmitTime: 0,
        throttleMs: throttleMs || this.defaultThrottleMs
      }
      
      this.channels.set(channelKey, channelConfig)
      console.log(`✅ RxJSChannelManager: Created channel ${channelKey}`)
      
      // Fetch historical data
      this.fetchAndReplayHistory(channelKey, channelConfig)
    } else if (throttleMs !== undefined) {
      // Update throttling if provided
      this.channels.get(channelKey)!.throttleMs = throttleMs
    }

    console.log(`📡 RxJSChannelManager: Subscribed to ${channelKey}`)

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
      console.warn(`❌ RxJSChannelManager: Channel ${channelKey} not found for replay`)
      return
    }

    if (channelConfig.cache.length > 0) {
      const message: ChannelMessage = {
        channel: channelKey,
        updateType: 'initial_data',
        data: [...channelConfig.cache]
      }
      
      this.channelSubject.next(message)
      console.log(`🔄 RxJSChannelManager: Replayed ${channelConfig.cache.length} cached points for ${channelKey}`)
    }
  }

  /**
   * Fetch historical data and replay to channel
   */
  private async fetchAndReplayHistory(channelKey: string, channelConfig: ChannelConfig) {
    try {
      console.log(`🔄 RxJSChannelManager: Fetching history for ${channelKey}`)
      
      const historyUrl = `/api/history/subscription/${channelConfig.marketId}?side=${channelConfig.side}&range=${channelConfig.range}&limit=${this.maxCacheSize}`
      
      // TODO: Implement actual fetch when API is available
      // const response = await fetch(historyUrl)
      // const historyData: DataPoint[] = await response.json()
      
      // For now, mock empty history
      const historyData: DataPoint[] = []
      
      if (historyData.length > 0) {
        // Store in cache
        channelConfig.cache = [...historyData]
        
        // Emit to channel
        const message: ChannelMessage = {
          channel: channelKey,
          updateType: 'initial_data',
          data: historyData
        }
        
        this.channelSubject.next(message)
        console.log(`✅ RxJSChannelManager: Replayed ${historyData.length} historical points for ${channelKey}`)
      } else {
        console.log(`📭 RxJSChannelManager: No historical data available for ${channelKey}`)
      }
      
    } catch (error) {
      console.error(`❌ RxJSChannelManager: Failed to fetch history for ${channelKey}:`, error)
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
      
      const parsed = this.parseChannelKey(channelKey)
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
    console.log(`🎯 RxJSChannelManager: Market subscribed - ${marketId} (${platform})`)
    
    // Create channels for all combinations of sides and ranges
    const sides: MarketSide[] = ['yes', 'no']
    const ranges: TimeRange[] = ['1D', '1W', '1M']
    
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
            cache: [],
            lastEmitTime: 0,
            throttleMs: this.defaultThrottleMs
          }
          
          this.channels.set(channelKey, channelConfig)
          channelsCreated++
          console.log(`✅ RxJSChannelManager: Created channel ${channelKey}`)
          
          // Fetch historical data for this channel
          this.fetchAndReplayHistory(channelKey, channelConfig)
        } else {
          console.log(`⚠️ RxJSChannelManager: Channel ${channelKey} already exists`)
        }
      }
    }
    
    console.log(`✅ RxJSChannelManager: Market ${marketId} configured with ${channelsCreated} new channels (${this.channels.size} total)`)
  }

  /**
   * Clean up resources
   */
  destroy() {
    console.log('🧹 RxJSChannelManager: Destroying manager')
    
    if (this.websocket) {
      this.websocket.removeEventListener('message', this.handleWebSocketMessage)
    }
    
    this.channelSubject.complete()
    this.websocketConnected.complete()
    this.channels.clear()
    
    console.log('✅ RxJSChannelManager: Cleanup complete')
  }
}

// Export singleton instance
export const rxjsChannelManager = new RxJSChannelManager()