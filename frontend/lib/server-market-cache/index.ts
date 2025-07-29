import { PolymarketServerCache } from './polymarket'
import { KalshiServerCache } from './kalshi'
import type { CachedMarket, SelectedToken, CacheStats } from './types'

/**
 * Main server market cache service that combines both platform-specific services
 */
export class ServerMarketCache {
  private polymarketCache: PolymarketServerCache
  private kalshiCache: KalshiServerCache

  constructor() {
    this.polymarketCache = new PolymarketServerCache()
    this.kalshiCache = new KalshiServerCache()
  }

  /**
   * Fetch markets from Polymarket CLOB API with cursor pagination
   */
  async fetchPolymarketMarkets(): Promise<CachedMarket[]> {
    return this.polymarketCache.fetchMarkets()
  }

  /**
   * Fetch markets from Kalshi API with cursor pagination
   */
  async fetchKalshiMarkets(): Promise<CachedMarket[]> {
    return this.kalshiCache.fetchMarkets()
  }

  /**
   * Update cache with fresh market data
   */
  async refreshCache(): Promise<void> {
    try {
      const polymarketMarkets = await this.fetchPolymarketMarkets()
      const kalshiMarkets = await this.fetchKalshiMarkets()
      
      // Update both caches
      await this.polymarketCache.refreshCache()
      await this.kalshiCache.refreshCache()

      //console.log(`Server cache updated with ${polymarketMarkets.length + kalshiMarkets.length} markets`)
    } catch (error) {
      console.error('Failed to refresh server cache:', error)
    }
  }

  /**
   * Search cached markets
   */
  searchMarkets(query: string, maxResults: number = 50): CachedMarket[] {
    const polymarketResults = this.polymarketCache.searchMarkets(query, Math.ceil(maxResults / 2))
    const kalshiResults = this.kalshiCache.searchMarkets(query, Math.ceil(maxResults / 2))
    
    const allResults = [...polymarketResults, ...kalshiResults]
    
    // Count markets by platform for debugging
    let polymarketCount = 0
    let kalshiCount = 0
    for (const market of allResults) {
      if (market.platform === 'polymarket') polymarketCount++
      if (market.platform === 'kalshi') kalshiCount++
    }

    //console.log(`🔍 Searching for "${query}" in ${allResults.length} cached markets (${polymarketCount} Polymarket, ${kalshiCount} Kalshi)`)

    // Sort by relevance (exact matches first, then by volume)
    return allResults.sort((a, b) => {
      const aExactMatch = a.title.toLowerCase() === query.toLowerCase()
      const bExactMatch = b.title.toLowerCase() === query.toLowerCase()
      
      if (aExactMatch && !bExactMatch) return -1
      if (!aExactMatch && bExactMatch) return 1
      
      return b.volume - a.volume
    }).slice(0, maxResults)
  }

  /**
   * Search cached markets filtered by platform
   */
  searchMarketsByPlatform(query: string, platform: 'polymarket' | 'kalshi', maxResults: number = 50): CachedMarket[] {
    if (platform === 'polymarket') {
      return this.searchPolymarketMarkets(query, maxResults)
    } else {
      return this.searchKalshiMarkets(query, maxResults)
    }
  }

  /**
   * Search Polymarket markets specifically
   */
  searchPolymarketMarkets(query: string, maxResults: number = 50): CachedMarket[] {
    return this.polymarketCache.searchPolymarketMarkets(query, maxResults)
  }

  /**
   * Search Kalshi markets specifically
   */
  searchKalshiMarkets(query: string, maxResults: number = 50): CachedMarket[] {
    return this.kalshiCache.searchKalshiMarkets(query, maxResults)
  }

  /**
   * Store selected token ID (stores both tokens from the pair)
   */
  storeSelectedToken(
    marketId: string,
    selectedTokenId: string,
    outcomeName: string,
    marketTitle: string
  ): void {
    // Try to find the market in either cache
    const polymarketMarket = this.polymarketCache.getMarket(marketId)
    const kalshiMarket = this.kalshiCache.getMarket(marketId)
    
    if (polymarketMarket) {
      this.polymarketCache.storeSelectedToken(marketId, selectedTokenId, outcomeName, marketTitle)
    } else if (kalshiMarket) {
      // For Kalshi, we'd need to implement the storeSelectedToken method
      console.warn('Kalshi token storage not implemented yet')
    } else {
      console.warn('Market not found for token storage:', marketId)
    }
  }

  /**
   * Get selected tokens
   */
  getSelectedTokens(): SelectedToken[] {
    const polymarketTokens = this.polymarketCache.getSelectedTokens()
    const kalshiTokens = this.kalshiCache.getSelectedTokens()
    
    return [...polymarketTokens, ...kalshiTokens]
  }

  /**
   * Remove selected token by market ID
   */
  removeSelectedToken(marketId: string): void {
    console.log('🗑️ Removing selected token from cache for market:', marketId)
    this.polymarketCache.removeSelectedToken(marketId)
    this.kalshiCache.removeSelectedToken(marketId)
  }

  /**
   * Get market by ID
   */
  getMarket(id: string): CachedMarket | undefined {
    return this.polymarketCache.getMarket(id) || this.kalshiCache.getMarket(id)
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): CacheStats {
    const polymarketStats = this.polymarketCache.getCacheStats()
    const kalshiStats = this.kalshiCache.getCacheStats()
    
    return {
      marketCount: polymarketStats.marketCount + kalshiStats.marketCount,
      selectedTokenCount: polymarketStats.selectedTokenCount + kalshiStats.selectedTokenCount,
      lastUpdate: new Date(Math.max(
        new Date(polymarketStats.lastUpdate).getTime(),
        new Date(kalshiStats.lastUpdate).getTime()
      )).toISOString(),
      cacheAge: Math.min(polymarketStats.cacheAge, kalshiStats.cacheAge),
      isStale: polymarketStats.isStale || kalshiStats.isStale
    }
  }

  /**
   * Clear all cached data
   */
  clearCache(): void {
    this.polymarketCache.clearCache()
    this.kalshiCache.clearCache()
    //console.log('Server cache cleared')
  }

  /**
   * Get Kalshi cache instance
   */
  getKalshiCache(): KalshiServerCache {
    return this.kalshiCache
  }

  /**
   * Get Polymarket cache instance
   */
  getPolymarketCache(): PolymarketServerCache {
    return this.polymarketCache
  }
}

// Singleton instance for server use
export const serverMarketCache = new ServerMarketCache()

// Export types and platform-specific services
export type { CachedMarket, SelectedToken, CacheStats } from './types'
export { PolymarketServerCache } from './polymarket'
export { KalshiServerCache } from './kalshi'