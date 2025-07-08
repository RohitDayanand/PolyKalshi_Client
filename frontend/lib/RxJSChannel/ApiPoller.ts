import { Subject } from 'rxjs'
import { DataPoint, ChannelConfig, ChannelMessage } from './types'
import { ChannelCache } from './ChannelCache'
import { DefaultParserFactory, ApiResponse } from './parsers'

/**
 * Handles REST API polling for historical data and updates
 */
export class ApiPoller {
  private pollIntervals = new Map<string, NodeJS.Timeout>()
  private maxCacheSize: number
  private channelCache: ChannelCache
  private channelSubject: Subject<ChannelMessage>
  private apiPollSize: Number
  private parserFactory: DefaultParserFactory

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
    this.parserFactory = new DefaultParserFactory()
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

      const parser = this.parserFactory.createParser(channelConfig.platform)
      const historyUrl = parser.buildApiUrl(channelConfig, 'initial')
      const response = await fetch(historyUrl)
      
      if (!response.ok) {
        throw new Error(`API request failed: ${response.status} ${response.statusText}`)
      }

      const apiResponse: ApiResponse = await response.json()
      
      if (!apiResponse.success) {
        throw new Error(`API returned error: ${apiResponse.error || 'Unknown error'}`)
      }
      
      //parser already preset to relevant platform
      const historyData: DataPoint[] = parser.parseHistoricalData(apiResponse, channelConfig.side)

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
      const parser = this.parserFactory.createParser(channelConfig.platform)
      const historyUrl = parser.buildApiUrl(channelConfig, 'update', lastDataTime)
      
      const response = await fetch(historyUrl)
      if (!response.ok) {
        throw new Error(`Poll request failed: ${response.status}`)
      }
      
      const apiResponse: ApiResponse = await response.json()
      
      if (!apiResponse.success) {
        console.warn(`Poll API returned error: ${apiResponse.error || 'Unknown error'}`)
        return // Skip this poll cycle
      }
      
      const newData: DataPoint[] = parser.parseHistoricalData(apiResponse, channelConfig.side)
      
      if (newData.length > 0) {
        console.log(`🔄 [POLL_UPDATE] Received ${newData.length} new points for ${channelKey}`)
        
        // @ERROR - this should HARD RESET cache - i.e use set initial data
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
   * Get polling statistics
   */
  getStats() {
    return {
      activePolls: this.pollIntervals.size,
      maxCacheSize: this.maxCacheSize
    }
  }
}