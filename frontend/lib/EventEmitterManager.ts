import { EventEmitter } from 'events'

// Types for data structures
export type TimeRange = '1D' | '1W' | '1M'
export type MarketSide = 'yes' | 'no'
export type UpdateType = 'initial_data' | 'update'

export interface DataPoint {
  time: number // Unix timestamp in seconds
  value: number // Price as decimal (0.0-1.0)
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

export interface EmitterCallback {
  (updateType: UpdateType, data: DataPoint | DataPoint[]): void
}

interface EmitterConfig {
  marketId: string
  side: MarketSide
  range: TimeRange
  emitter: EventEmitter
  cache: DataPoint[]
  lastEmitTime: number
  throttleMs: number
  isActive: boolean
}

interface MarketConfig {
  marketId: string
  platform: 'polymarket' | 'kalshi'
  emitters: Map<string, EmitterConfig> // key: "side:range"
}

export class EventEmitterManager {
  private websocket: WebSocket | null = null
  private markets: Map<string, MarketConfig> = new Map() // key: marketId
  private maxCacheSize: number = 300
  private defaultThrottleMs: number = 1000

  // Time range interval mappings (in minutes)
  private intervalMappings: Record<TimeRange, number> = {
    '1D': 1,     // 1 minute intervals
    '1W': 30,    // 30 minute intervals  
    '1M': 60     // 1 hour intervals
  }

  constructor(maxCacheSize: number = 300, defaultThrottleMs: number = 1000) {
    this.maxCacheSize = maxCacheSize
    this.defaultThrottleMs = defaultThrottleMs
  }

  /**
   * Set the WebSocket instance from the existing singleton
   */
  setWebSocketInstance(ws: WebSocket | null) {
    console.log('📡 EventEmitterManager: Setting WebSocket instance')
    
    // Clean up existing listener if any
    if (this.websocket) {
      this.websocket.removeEventListener('message', this.handleWebSocketMessage)
    }

    this.websocket = ws
    
    if (this.websocket) {
      this.websocket.addEventListener('message', this.handleWebSocketMessage)
      console.log('✅ EventEmitterManager: WebSocket listener attached')
    }
  }

  /**
   * Handle incoming WebSocket messages - bound method to preserve 'this'
   */
  private handleWebSocketMessage = (event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data)
      
      if (message.type === 'ticker_update') {
        this.processTickerUpdate(message as TickerData)
      }
    } catch (error) {
      console.error('❌ EventEmitterManager: Error processing WebSocket message:', error)
    }
  }

  /**
   * Process incoming ticker updates and route to appropriate emitters
   */
  private processTickerUpdate(tickerData: TickerData) {
    const marketId = tickerData.market_id
    const market = this.markets.get(marketId)
    
    if (!market) {
      console.log(`📊 EventEmitterManager: No market config for ${marketId}, skipping tick`)
      return
    }

    console.log(`📊 EventEmitterManager: Processing ticker for ${marketId}`)

    // Process both sides
    this.processSideUpdate(market, 'yes', tickerData)
    this.processSideUpdate(market, 'no', tickerData)
  }

  /**
   * Process ticker update for a specific side (yes/no)
   */
  private processSideUpdate(market: MarketConfig, side: MarketSide, tickerData: TickerData) {
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
      const emitterKey = `${side}:${range}`
      const emitterConfig = market.emitters.get(emitterKey)
      
      if (emitterConfig) {
        this.emitToEmitter(emitterConfig, dataPoint)
      }
    }
  }

  /**
   * Emit data point to specific emitter with throttling
   */
  private emitToEmitter(emitterConfig: EmitterConfig, dataPoint: DataPoint) {
    const now = Date.now()
    
    // Add to cache
    emitterConfig.cache.push(dataPoint)
    if (emitterConfig.cache.length > this.maxCacheSize) {
      emitterConfig.cache.shift()
    }

    // Check throttling
    if (now - emitterConfig.lastEmitTime < emitterConfig.throttleMs) {
      console.log(`⏱️ EventEmitterManager: Throttling emission for ${emitterConfig.marketId}:${emitterConfig.side}:${emitterConfig.range}`)
      return
    }

    emitterConfig.lastEmitTime = now
    emitterConfig.emitter.emit('data', 'update', dataPoint)
    
    console.log(`📤 EventEmitterManager: Emitted update for ${emitterConfig.marketId}:${emitterConfig.side}:${emitterConfig.range}`)
  }

  /**
   * Called by Redux middleware when a market gets marked as subscribed
   */
  onMarketSubscribed(marketId: string, platform: 'polymarket' | 'kalshi') {
    console.log(`🎯 EventEmitterManager: Market subscribed - ${marketId}`)
    
    if (this.markets.has(marketId)) {
      console.log(`⚠️ EventEmitterManager: Market ${marketId} already exists, skipping creation`)
      return
    }

    // Create market configuration with all emitters
    const market: MarketConfig = {
      marketId,
      platform,
      emitters: new Map()
    }

    // Create emitters for all combinations of sides and ranges
    for (const side of ['yes', 'no'] as MarketSide[]) {
      for (const range of ['1D', '1W', '1M'] as TimeRange[]) {
        const emitterKey = `${side}:${range}`
        const emitter = new EventEmitter()
        
        const emitterConfig: EmitterConfig = {
          marketId,
          side,
          range,
          emitter,
          cache: [],
          lastEmitTime: 0,
          throttleMs: this.defaultThrottleMs,
          isActive: false
        }
        
        market.emitters.set(emitterKey, emitterConfig)
        console.log(`✅ EventEmitterManager: Created emitter ${marketId}:${emitterKey}`)
      }
    }

    this.markets.set(marketId, market)
    console.log(`✅ EventEmitterManager: Market ${marketId} fully configured with ${market.emitters.size} emitters`)
  }

  /**
   * Subscribe to market data for specific side and time range
   */
  subscribe(
    marketId: string, 
    side: MarketSide, 
    range: TimeRange, 
    callback: EmitterCallback,
    throttleMs?: number
  ): string | null {
    const market = this.markets.get(marketId)
    if (!market) {
      console.error(`❌ EventEmitterManager: Market ${marketId} not found`)
      return null
    }

    const emitterKey = `${side}:${range}`
    const emitterConfig = market.emitters.get(emitterKey)
    if (!emitterConfig) {
      console.error(`❌ EventEmitterManager: Emitter ${marketId}:${emitterKey} not found`)
      return null
    }

    // Set custom throttling if provided
    if (throttleMs !== undefined) {
      emitterConfig.throttleMs = throttleMs
    }

    emitterConfig.isActive = true
    
    // Set up the listener
    const subscriptionKey = `${marketId}:${emitterKey}:${Date.now()}`
    emitterConfig.emitter.on('data', callback)

    console.log(`📡 EventEmitterManager: Subscribed to ${marketId}:${emitterKey}`)

    // Fetch and replay historical data
    this.fetchAndReplayHistory(emitterConfig, callback)

    return subscriptionKey
  }

  /**
   * Unsubscribe from market data
   */
  unsubscribe(marketId: string, side: MarketSide, range: TimeRange, callback: EmitterCallback) {
    const market = this.markets.get(marketId)
    if (!market) return

    const emitterKey = `${side}:${range}`
    const emitterConfig = market.emitters.get(emitterKey)
    if (!emitterConfig) return

    emitterConfig.emitter.off('data', callback)
    
    // Mark as inactive if no more listeners
    if (emitterConfig.emitter.listenerCount('data') === 0) {
      emitterConfig.isActive = false
    }

    console.log(`📡 EventEmitterManager: Unsubscribed from ${marketId}:${emitterKey}`)
  }

  /**
   * Manually replay historical data for a subscription
   */
  replay(marketId: string, side: MarketSide, range: TimeRange, callback: EmitterCallback) {
    const market = this.markets.get(marketId)
    if (!market) return

    const emitterKey = `${side}:${range}`
    const emitterConfig = market.emitters.get(emitterKey)
    if (!emitterConfig) return

    // Replay from cache
    if (emitterConfig.cache.length > 0) {
      callback('initial_data', [...emitterConfig.cache])
      console.log(`🔄 EventEmitterManager: Replayed ${emitterConfig.cache.length} cached points for ${marketId}:${emitterKey}`)
    }
  }

  /**
   * Fetch historical data and replay to callback
   */
  private async fetchAndReplayHistory(emitterConfig: EmitterConfig, callback: EmitterCallback) {
    try {
      // Mock REST API endpoints that should be implemented:
      // GET /api/history/market/{marketId}/side/{side}/range/{range}
      // GET /api/history/subscription/{backendMarketId}?side={side}&range={range}&limit=300
      
      console.log(`🔄 EventEmitterManager: Fetching history for ${emitterConfig.marketId}:${emitterConfig.side}:${emitterConfig.range}`)
      
      const market = this.markets.get(emitterConfig.marketId)
      if (!market) return

      const historyUrl = `/api/history/subscription/${market.marketId}?side=${emitterConfig.side}&range=${emitterConfig.range}&limit=${this.maxCacheSize}`
      
      // TODO: Implement actual fetch
      // const response = await fetch(historyUrl)
      // const historyData: DataPoint[] = await response.json()
      
      // For now, mock empty history
      const historyData: DataPoint[] = []
      
      if (historyData.length > 0) {
        // Store in cache
        emitterConfig.cache = [...historyData]
        
        // Replay to callback
        callback('initial_data', historyData)
        console.log(`✅ EventEmitterManager: Replayed ${historyData.length} historical points`)
      } else {
        console.log(`📭 EventEmitterManager: No historical data available`)
      }
      
    } catch (error) {
      console.error(`❌ EventEmitterManager: Failed to fetch history:`, error)
    }
  }


  /**
   * Get statistics about the manager
   */
  getStats() {
    const stats = {
      totalMarkets: this.markets.size,
      totalEmitters: 0,
      activeEmitters: 0,
      totalCacheSize: 0,
      markets: [] as any[]
    }

    for (const [frontendId, market] of this.markets.entries()) {
      stats.totalEmitters += market.emitters.size
      
      let marketCacheSize = 0
      let activeEmittersCount = 0
      
      for (const emitterConfig of market.emitters.values()) {
        marketCacheSize += emitterConfig.cache.length
        if (emitterConfig.isActive) {
          activeEmittersCount++
        }
      }
      
      stats.activeEmitters += activeEmittersCount
      stats.totalCacheSize += marketCacheSize
      
      stats.markets.push({
        frontendId,
        backendMarketId: market.backendMarketId,
        platform: market.platform,
        emittersCount: market.emitters.size,
        activeEmitters: activeEmittersCount,
        cacheSize: marketCacheSize
      })
    }

    return stats
  }

  /**
   * Clean up resources
   */
  destroy() {
    console.log('🧹 EventEmitterManager: Destroying manager')
    
    if (this.websocket) {
      this.websocket.removeEventListener('message', this.handleWebSocketMessage)
    }
    
    // Clean up all emitters
    for (const market of this.markets.values()) {
      for (const emitterConfig of market.emitters.values()) {
        emitterConfig.emitter.removeAllListeners()
      }
    }
    
    this.markets.clear()
    console.log('✅ EventEmitterManager: Cleanup complete')
  }
}

// Export singleton instance
export const eventEmitterManager = new EventEmitterManager()