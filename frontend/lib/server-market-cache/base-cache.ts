import type { CachedMarket, SelectedToken, CacheStats } from './types'

/**
 * Base cache service with common functionality
 */
export abstract class BaseServerMarketCache {
  protected memoryCache: Map<string, CachedMarket> = new Map()
  protected selectedTokens: Map<string, SelectedToken> = new Map()
  protected lastUpdate: number = 0
  protected cacheLifetime: number = 30 * 60 * 1000 // 30 minutes

  /**
   * Parse number from various formats
   */
  protected parseNumber(value: any): number {
    if (typeof value === 'number') return value
    if (typeof value === 'string') {
      const parsed = parseFloat(value)
      return isNaN(parsed) ? 0 : parsed
    }
    return 0
  }

  /**
   * Get market by ID
   */
  getMarket(id: string): CachedMarket | undefined {
    console.log('🔍 DEBUG BaseCache.getMarket called with:', id, 'type:', typeof id)
    console.log('🔍 DEBUG Cache size:', this.memoryCache.size)
    console.log('🔍 DEBUG First 5 cache keys:', Array.from(this.memoryCache.keys()).slice(0, 5))
    
    const result = this.memoryCache.get(id)
    console.log('🔍 DEBUG getMarket result:', result ? 'Found' : 'Not found')
    
    return result
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): CacheStats {
    return {
      marketCount: this.memoryCache.size,
      selectedTokenCount: this.selectedTokens.size,
      lastUpdate: new Date(this.lastUpdate).toISOString(),
      cacheAge: Date.now() - this.lastUpdate,
      isStale: Date.now() - this.lastUpdate > this.cacheLifetime
    }
  }

  /**
   * Clear all cached data
   */
  clearCache(): void {
    this.memoryCache.clear()
    this.selectedTokens.clear()
    this.lastUpdate = 0
  }

  /**
   * Get selected tokens
   */
  getSelectedTokens(): SelectedToken[] {
    return Array.from(this.selectedTokens.values())
  }

  /**
   * Search cached markets
   */
  searchMarkets(query: string, maxResults: number = 50): CachedMarket[] {
    const results: CachedMarket[] = []
    const lowercaseQuery = query.toLowerCase()

    for (const market of this.memoryCache.values()) {
      if (results.length >= maxResults) break

      const titleMatch = market.title?.toLowerCase().includes(lowercaseQuery) || false
      const slugMatch = market.slug?.toLowerCase().includes(lowercaseQuery) || false

      if (titleMatch || slugMatch) {
        results.push(market)
      }
    }

    // Sort by relevance (exact matches first, then by volume)
    return results.sort((a, b) => {
      const aExactMatch = a.title.toLowerCase() === lowercaseQuery
      const bExactMatch = b.title.toLowerCase() === lowercaseQuery
      
      if (aExactMatch && !bExactMatch) return -1
      if (!aExactMatch && bExactMatch) return 1
      
      return b.volume - a.volume
    })
  }

  /**
   * Abstract method to fetch platform-specific markets
   */
  abstract fetchMarkets(): Promise<CachedMarket[]>

  /**
   * Abstract method to transform API response to cached market format
   */
  abstract transformApiResponse(apiData: any): CachedMarket[]
}