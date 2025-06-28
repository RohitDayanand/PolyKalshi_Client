import { Subject } from 'rxjs'
import { DataPoint, ChannelConfig, ChannelMessage, MarketSide } from './types'
import { ChannelCache } from './ChannelCache'

// Kalshi API response types
interface KalshiCandlestickResponse {
  success: boolean
  data?: any
  error?: string
  market_info: Record<string, string>
}

/**
 * Handles REST API polling for historical data and updates
 */
export class ApiPoller {
  private pollIntervals = new Map<string, NodeJS.Timeout>()
  private maxCacheSize: number
  private channelCache: ChannelCache
  private channelSubject: Subject<ChannelMessage>
  private apiPollSize: Number 

  constructor(
    channelSubject: Subject<ChannelMessage>,
    channelCache: ChannelCache,
    maxCacheSize: number = 300,
    apiPollSize: number

  ) {
    this.channelSubject = channelSubject
    this.channelCache = channelCache
    this.maxCacheSize = maxCacheSize
    this.apiPollSize = apiPollSize
  }

  /**
   * Fetch initial historical data for a channel
   */
  async fetchInitialData(channelKey: string, channelConfig: ChannelConfig): Promise<void> {
    try {
      console.log(`🔄 [API_POLL] Fetching initial history for ${channelKey}`, {
        marketId: channelConfig.marketId,
        platform: channelConfig.platform,
        side: channelConfig.side,
        range: channelConfig.range
      })

      const historyUrl = this.buildApiUrl(channelConfig, 'initial')
      const response = await fetch(historyUrl)
      
      if (!response.ok) {
        throw new Error(`API request failed: ${response.status} ${response.statusText}`)
      }

      const kalshiResponse: KalshiCandlestickResponse = await response.json()
      
      if (!kalshiResponse.success) {
        throw new Error(`API returned error: ${kalshiResponse.error || 'Unknown error'}`)
      }
      
      const historyData: DataPoint[] = this.processKalshiCandlesticks(kalshiResponse, channelConfig.side)

      if (historyData.length > 0) {
        console.log(`✅ [API_POLL] Received ${historyData.length} historical points for ${channelKey}`)
        
        // Store in cache
        this.channelCache.setInitialData(channelConfig, historyData)
        channelConfig.lastApiPoll = Date.now()

        // Emit initial data to subscribers
        this.emitInitialData(channelKey, historyData)

        // Start periodic polling
        this.startPolling(channelKey, channelConfig)
      } else {
        console.log(`📭 [API_POLL] No historical data available for ${channelKey}`)
        // Still start polling for future data
        this.startPolling(channelKey, channelConfig)
      }

    } catch (error) {
      console.error(`❌ [API_POLL] Failed to fetch initial history for ${channelKey}:`, error)
      // Start polling anyway to retry
      this.startPolling(channelKey, channelConfig)
    }
  }

  /**
   * Start periodic polling for a channel
   */
  startPolling(channelKey: string, channelConfig: ChannelConfig): void {
    if (channelConfig.isPolling) {
      console.log(`⚠️ [POLLING] Channel ${channelKey} already polling, skipping`)
      return
    }

    channelConfig.isPolling = true
    
    const pollInterval = setInterval(async () => {
      await this.pollForUpdates(channelKey, channelConfig)
    }, channelConfig.apiPollInterval)
    
    this.pollIntervals.set(channelKey, pollInterval)
    console.log(`🔄 [POLLING_STARTED] Polling every ${channelConfig.apiPollInterval}ms for ${channelKey}`)
  }

  /**
   * Stop polling for a specific channel
   */
  stopPolling(channelKey: string, channelConfig?: ChannelConfig): void {
    const interval = this.pollIntervals.get(channelKey)
    if (interval) {
      clearInterval(interval)
      this.pollIntervals.delete(channelKey)
      
      if (channelConfig) {
        channelConfig.isPolling = false
      }
      
      console.log(`🛑 [POLLING_STOPPED] Stopped polling for ${channelKey}`)
    }
  }

  /**
   * Poll for new data updates
   */
  private async pollForUpdates(channelKey: string, channelConfig: ChannelConfig): Promise<void> {
    try {
      const lastDataTime = this.channelCache.getLatestTimestamp(channelConfig)
      const historyUrl = this.buildApiUrl(channelConfig, 'update', lastDataTime)
      
      const response = await fetch(historyUrl)
      if (!response.ok) {
        throw new Error(`Poll request failed: ${response.status}`)
      }
      
      const kalshiResponse: KalshiCandlestickResponse = await response.json()
      
      if (!kalshiResponse.success) {
        console.warn(`Poll API returned error: ${kalshiResponse.error || 'Unknown error'}`)
        return // Skip this poll cycle
      }
      
      const newData: DataPoint[] = this.processKalshiCandlesticks(kalshiResponse, channelConfig.side)
      
      if (newData.length > 0) {
        console.log(`🔄 [POLL_UPDATE] Received ${newData.length} new points for ${channelKey}`)
        
        // Add to cache
        this.channelCache.addDataPoints(channelConfig, newData)
        channelConfig.lastApiPoll = Date.now()

        // Emit individual updates
        this.emitUpdates(channelKey, newData)
      }
      
    } catch (error) {
      console.error(`❌ [POLL_ERROR] Failed to poll ${channelKey}:`, error)
    }
  }

  /**
   * Build API URL for fetching data from Kalshi candlesticks endpoint
   */
  private buildApiUrl(channelConfig: ChannelConfig, type: 'initial' | 'update', since?: number): string {
    if (channelConfig.platform !== 'kalshi') {
      throw new Error(`Platform ${channelConfig.platform} not supported yet. Only 'kalshi' is currently supported.`)
    }

    // @TODO merge this baseUrl
    const baseUrl = 'http://localhost:8000/api/kalshi/candlesticks'
    const marketStringId = `${channelConfig.marketId}&${channelConfig.side}&${channelConfig.range}`
    
    // Calculate time range based on range parameter
    const { startTs, endTs } = this.calculateTimeRange(channelConfig.range, type, since)
    
    const params = new URLSearchParams({
      market_string_id: marketStringId,
      start_ts: startTs.toString(),
      end_ts: endTs.toString()
    })

    return `${baseUrl}?${params.toString()}`
  }

  /**
   * Calculate Unix timestamp range based on TimeRange and request type
   * 
   * @TODO move this to to the backend - amount of historical data recieved by clients should be universal
   */
  private calculateTimeRange(range: string, type: 'initial' | 'update', since?: number): { startTs: number, endTs: number } {
    const nowTs = Math.floor(Date.now() / 1000) // Unix seconds
    const endTs = nowTs
    
    let startTs: number
    
    if (type === 'update' && since) {
      // For updates, use the 'since' timestamp as start
      startTs = Math.floor(since / 1000) // Convert from milliseconds to seconds if needed
    } else {
      // For initial data, calculate based on range
      switch (range) {
        case '1H':
          startTs = nowTs - (60 * 60 * 6) // 6 hour ago
          break
        case '1W':
          startTs = nowTs - (7 * 24 * 60 * 60 * 2) // 2 week ago
          break
        case '1M':
          startTs = nowTs - (30 * 24 * 60 * 60 * 6) // 6 months ago
          break
        case '1Y':
          startTs = nowTs - (365 * 24 * 60 * 60) // 365 days ago
          break
        default:
          console.warn(`Unknown range ${range}, defaulting to 1 hour`)
          startTs = nowTs - (60 * 60)
      }
    }
    
    return { startTs, endTs }
  }

  /**
   * Emit initial data to channel subscribers
   */
  private emitInitialData(channelKey: string, data: DataPoint[]): void {
    const message: ChannelMessage = {
      channel: channelKey,
      updateType: 'initial_data',
      data: data
    }
    
    this.channelSubject.next(message)
    console.log(`📡 [INITIAL_DATA_EMITTED] Sent ${data.length} points to ${channelKey} subscribers`)
  }

  /**
   * Emit update data to channel subscribers
   */
  private emitUpdates(channelKey: string, data: DataPoint[]): void {
    data.forEach(point => {
      const message: ChannelMessage = {
        channel: channelKey,
        updateType: 'update',
        data: point
      }
      this.channelSubject.next(message)
    })
  }

  /**
   * Stop all polling intervals and clean up
   */
  destroy(): void {
    console.log('🧹 [API_POLLER] Stopping all polling intervals...')
    
    this.pollIntervals.forEach((interval, channelKey) => {
      clearInterval(interval)
      console.log(`🛑 [API_POLLER] Stopped polling for ${channelKey}`)
    })
    
    this.pollIntervals.clear()
    console.log('✅ [API_POLLER] All polling stopped')
  }

  /**
   * Process Kalshi candlestick response into DataPoint format
   */
  private processKalshiCandlesticks(kalshiResponse: KalshiCandlestickResponse, side: MarketSide): DataPoint[] {
    if (!kalshiResponse.data || !kalshiResponse.data.candlesticks) {
      console.warn('No candlesticks data in Kalshi response')
      return []
    }
    
    const candlesticks = kalshiResponse.data.candlesticks
    
    return candlesticks.map((candle: any) => ({
      time: candle.time, // Convert Unix seconds to milliseconds
      value: candle[`price_${side}`],
      volume: candle.volume
    }))
  }

  /**
   * Get polling statistics
   */
  getStats() {
    return {
      activePolls: this.pollIntervals.size,
      maxCacheSize: this.maxCacheSize
    }
  }
}