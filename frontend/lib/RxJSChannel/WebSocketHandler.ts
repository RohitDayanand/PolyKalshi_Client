import { Subject, BehaviorSubject } from 'rxjs'
import { TIME_RANGES } from '../ChartStuff/chart-types'
import { DataPoint, TickerData, ChannelMessage, ChannelConfig, MarketSide } from './types'
import { ChannelCache } from './ChannelCache'

/**
 * Handles WebSocket connections and message processing
 */
export class WebSocketHandler {
  private websocket: WebSocket | null = null
  private websocketConnected: BehaviorSubject<boolean>
  private channelSubject: Subject<ChannelMessage>
  private channels: Map<string, ChannelConfig>
  private channelCache: ChannelCache

  constructor(
    websocketConnected: BehaviorSubject<boolean>,
    channelSubject: Subject<ChannelMessage>,
    channels: Map<string, ChannelConfig>,
    channelCache: ChannelCache
  ) {
    this.websocketConnected = websocketConnected
    this.channelSubject = channelSubject
    this.channels = channels
    this.channelCache = channelCache
  }

  /**
   * Set WebSocket instance from existing singleton
   */
  setWebSocketInstance(ws: WebSocket | null): void {
    // Clean up existing listener
    if (this.websocket) {
      this.websocket.removeEventListener('message', this.handleWebSocketMessage)
    }

    this.websocket = ws
    
    if (this.websocket) {
      this.websocket.addEventListener('message', this.handleWebSocketMessage)
      this.websocketConnected.next(true)
      console.log('✅ [WEBSOCKET_HANDLER] WebSocket listener attached')
    } else {
      this.websocketConnected.next(false)
      console.log('📡 [WEBSOCKET_HANDLER] WebSocket disconnected')
    }
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleWebSocketMessage = (event: MessageEvent) => {
    console.log('📨 [WEBSOCKET_HANDLER] Raw message received:', event.data)
    try {
      const message = JSON.parse(event.data)
      console.log('📨 [WEBSOCKET_HANDLER] Parsed message:', message)
      
      if (message.type === 'ticker_update') {
        console.log('📊 [WEBSOCKET_HANDLER] Processing ticker_update message')
        this.processTickerUpdate(message as TickerData)
      } else {
        console.log('📨 [WEBSOCKET_HANDLER] Ignoring message type:', message.type)
      }
    } catch (error) {
      console.error('❌ [WEBSOCKET_HANDLER] Error processing message:', error, 'Raw data:', event.data)
    }
  }

  /**
   * Process incoming ticker updates and route to appropriate channels
   */
  private processTickerUpdate(tickerData: TickerData): void {
    const marketId = tickerData.market_id
    
    console.log(`📊 [WEBSOCKET_HANDLER] Processing ticker for ${marketId}`)

    // Process both sides (yes/no)
    this.processSideUpdate(marketId, 'yes', tickerData)
    this.processSideUpdate(marketId, 'no', tickerData)
  }

  /**
   * Process ticker update for a specific side (yes/no)
   */
  private processSideUpdate(marketId: string, side: MarketSide, tickerData: TickerData): void {
    const sideData = tickerData.summary_stats[side]
    if (!sideData) return

    // @TODO add a utility midpoint function calculation
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
    for (const range of TIME_RANGES) {
      const channelKey = ChannelCache.generateChannelKey(marketId, side, range)
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
  private emitToChannel(channelKey: string, channelConfig: ChannelConfig, dataPoint: DataPoint): void {
    const now = Date.now()
    
    // Add to cache using ChannelCache
    this.channelCache.addDataPoint(channelConfig, dataPoint)

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
    
    console.log(`📡 [DATA_EMITTED] WebSocket message sent to subscribers:`, {
      channel: channelKey,
      updateType: message.updateType,
      dataPoint: { time: dataPoint.time, value: dataPoint.value },
      lruCacheSize: channelConfig.lruCache.size,
      timeSinceLastEmit: now - (channelConfig.lastEmitTime - channelConfig.throttleMs)
    })
    
    this.channelSubject.next(message)
  }

  /**
   * Get WebSocket connection status
   */
  isConnected(): boolean {
    return this.websocketConnected.value
  }

  /**
   * Get connection status observable
   */
  getConnectionStatus() {
    return this.websocketConnected.asObservable()
  }

  /**
   * Clean up WebSocket resources
   */
  destroy(): void {
    console.log('🧹 [WEBSOCKET_HANDLER] Cleaning up WebSocket...')
    
    if (this.websocket) {
      this.websocket.removeEventListener('message', this.handleWebSocketMessage)
      console.log('🔌 [WEBSOCKET_HANDLER] Removed WebSocket listener')
    }
    
    this.websocket = null
    this.websocketConnected.next(false)
    console.log('✅ [WEBSOCKET_HANDLER] WebSocket cleanup complete')
  }

  /**
   * Get handler statistics
   */
  getStats() {
    return {
      connected: this.websocketConnected.value,
      websocketInstance: !!this.websocket
    }
  }
}