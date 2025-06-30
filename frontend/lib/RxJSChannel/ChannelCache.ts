import { LRUCache } from 'lru-cache'
import { DataPoint, ChannelConfig, MarketSide, TimeRange } from './types'

/**
 * Handles caching operations for channel data using LRU cache
 */
export class ChannelCache {
  private maxCacheSize: number

  constructor(maxCacheSize: number = 300) {
    this.maxCacheSize = maxCacheSize
  }

  /**
   * Create a new LRU cache instance for a channel
   */
  createLRUCache(): LRUCache<number, DataPoint> {
    return new LRUCache<number, DataPoint>({
      max: this.maxCacheSize,
      ttl: 1000 * 60 * 60 // 1 hour TTL
    })
  }

  /**
   * Add a data point to channel cache (LRU only)
   */
  addDataPoint(channelConfig: ChannelConfig, dataPoint: DataPoint): void {
    // Add to LRU cache
    channelConfig.lruCache.set(dataPoint.time, dataPoint)
  }

  /**
   * Add multiple data points to channel cache
   */
  addDataPoints(channelConfig: ChannelConfig, dataPoints: DataPoint[]): void {
    dataPoints.forEach(point => {
      if (!channelConfig.lruCache.has(point.time)) {
        this.addDataPoint(channelConfig, point)
      }
    })
  }

  /**
   * Set initial data for a channel (replaces existing cache)
   */
  setInitialData(channelConfig: ChannelConfig, dataPoints: DataPoint[]): void {
    // Clear existing cache
    channelConfig.lruCache.clear()
    
    // Add all data points
    dataPoints.forEach(point => {
      channelConfig.lruCache.set(point.time, point)
    })
  }

  /**
   * Get all cached data points sorted by timestamp
   */
  getCachedData(channelConfig: ChannelConfig): DataPoint[] {
    const cacheEntries = Array.from(channelConfig.lruCache.entries())
    return cacheEntries
      .sort(([a], [b]) => a - b) // Sort by timestamp
      .map(([_, dataPoint]) => dataPoint)
  }

  /**
   * Get the most recent data point from cache
   */
  getLatestDataPoint(channelConfig: ChannelConfig): DataPoint | undefined {
    if (channelConfig.lruCache.size === 0) return undefined
    
    const timestamps = Array.from(channelConfig.lruCache.keys())
    const latestTimestamp = Math.max(...timestamps)
    return channelConfig.lruCache.get(latestTimestamp)
  }

  /**
   * Get the latest timestamp in cache (for polling since parameter)
   */
  getLatestTimestamp(channelConfig: ChannelConfig): number {
    if (channelConfig.lruCache.size === 0) return 0
    return Math.max(...Array.from(channelConfig.lruCache.keys()))
  }

  /**
   * Check if channel has cached data
   */
  hasData(channelConfig: ChannelConfig): boolean {
    return channelConfig.lruCache.size > 0
  }

  /**
   * Get cache statistics for a channel
   */
  getCacheStats(channelConfig: ChannelConfig) {
    return {
      lruCacheSize: channelConfig.lruCache.size,
      oldestTimestamp: channelConfig.lruCache.size > 0 
        ? Math.min(...Array.from(channelConfig.lruCache.keys())) 
        : 0,
      newestTimestamp: this.getLatestTimestamp(channelConfig)
    }
  }

  /**
   * Clear all cache data for a channel
   */
  clearCache(channelConfig: ChannelConfig): void {
    channelConfig.lruCache.clear()
  }

  /**
   * @TODO merge into main function utility
   * Generate channel key from components
   */
  static generateChannelKey(marketId: string, side: MarketSide, range: TimeRange): string {
    return `${marketId}&${side}&${range}`
  }

  /**
   * @TODO merge into main function utility
   * Parse channel key back to components
   */
  static parseChannelKey(channelKey: string): { marketId: string; side: MarketSide; range: TimeRange } | null {
    const parts = channelKey.split('&')
    if (parts.length !== 3) {
      console.warn(`[CHANNEL_CACHE] Invalid channel key format: ${channelKey}`)
      return null
    }
    
    const [marketId, side, range] = parts
    return {
      marketId,
      side: side as MarketSide,
      range: range as TimeRange
    }
  }
}