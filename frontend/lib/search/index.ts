import type { Market } from '@/types/market'
import type { SearchConfig } from './types'
import { PolymarketSearchService } from './polymarket/polymarket-search'
import { KalshiSearchService } from './kalshi/kalshi-search'

/**
 * Main search service class that combines both platform-specific services
 */
export class MarketSearchService {
  private polymarketService: PolymarketSearchService
  private kalshiService: KalshiSearchService

  constructor(config: Partial<SearchConfig> = {}) {
    this.polymarketService = new PolymarketSearchService(config)
    this.kalshiService = new KalshiSearchService(config)
  }

  /**
   * Search Polymarket questions
   */
  async searchPolymarketQuestions(query: string): Promise<Market[]> {
    return this.polymarketService.searchQuestions(query)
  }

  /**
   * Search Kalshi questions
   */
  async searchKalshiQuestions(query: string): Promise<Market[]> {
    return this.kalshiService.searchQuestions(query)
  }

  /**
   * Update search configuration for both services
   */
  updateConfig(newConfig: Partial<SearchConfig>): void {
    this.polymarketService.updateConfig(newConfig)
    this.kalshiService.updateConfig(newConfig)
  }

  /**
   * Get current search configuration
   */
  getConfig(): SearchConfig {
    return this.polymarketService.getConfig()
  }

  /**
   * Store selected token ID when user clicks on a market
   */
  async storeSelectedToken(marketId: string, tokenId: string, outcomeName: string, marketTitle: string): Promise<void> {
    // Determine platform from marketId and use appropriate service
    if (marketId.startsWith('poly_') || marketId.includes('polymarket')) {
      return this.polymarketService.storeSelectedToken(marketId, tokenId, outcomeName, marketTitle)
    } else {
      // Assume Kalshi for non-polymarket IDs
      return this.kalshiService.storeSelectedToken(marketId, tokenId, outcomeName, marketTitle)
    }
  }

  /**
   * Get all selected tokens
   */
  async getSelectedTokens() {
    // Get tokens from both services and combine them
    const [polymarketTokens, kalshiTokens] = await Promise.all([
      this.polymarketService.getSelectedTokens(),
      this.kalshiService.getSelectedTokens()
    ])
    return [...polymarketTokens, ...kalshiTokens]
  }

  /**
   * Remove selected token by market ID
   */
  async removeSelectedToken(marketId: string): Promise<void> {
    // Remove from both services since we don't know which platform the market belongs to
    await Promise.all([
      this.polymarketService.removeSelectedToken(marketId),
      this.kalshiService.removeSelectedToken(marketId)
    ])
  }

  /**
   * Get cache statistics
   */
  async getCacheStats() {
    // Get stats from both services and combine them
    const [polymarketStats, kalshiStats] = await Promise.all([
      this.polymarketService.getCacheStats(),
      this.kalshiService.getCacheStats()
    ])
    
    return {
      marketCount: polymarketStats.marketCount + kalshiStats.marketCount,
      selectedTokenCount: polymarketStats.selectedTokenCount + kalshiStats.selectedTokenCount,
      lastUpdate: new Date(Math.max(
        new Date(polymarketStats.lastUpdate).getTime(),
        new Date(kalshiStats.lastUpdate).getTime()
      )).toISOString(),
      cacheAge: Math.min(polymarketStats.cacheAge, kalshiStats.cacheAge),
      isStale: polymarketStats.isStale || kalshiStats.isStale,
      polymarketStats,
      kalshiStats
    }
  }

  /**
   * Get market by ID
   */
  async getMarket(id: string) {
    console.log('🔍 DEBUG MarketSearchService.getMarket called with:', id, 'type:', typeof id)
    
    // Try to get market from appropriate service based on ID
    let result = null
    if (id.startsWith('poly_') || id.includes('polymarket')) {
      result = await this.polymarketService.getMarket(id)
    } else {
      result = await this.kalshiService.getMarket(id)
    }
    
    // If not found in expected service, try the other one as fallback
    if (!result) {
      if (id.startsWith('poly_') || id.includes('polymarket')) {
        result = await this.kalshiService.getMarket(id)
      } else {
        result = await this.polymarketService.getMarket(id)
      }
    }
    
    console.log('🔍 DEBUG MarketSearchService.getMarket result:', result ? 'Found' : 'Not found')
    return result
  }

  /**
   * Clear cache
   */
  async clearCache() {
    // Clear cache from both services
    await Promise.all([
      this.polymarketService.clearCache(),
      this.kalshiService.clearCache()
    ])
  }
}

// Export a default instance
export const marketSearchService = new MarketSearchService()

// Export types for use in other files
export type { SearchConfig } from './types'
export { PolymarketSearchService, KalshiSearchService }