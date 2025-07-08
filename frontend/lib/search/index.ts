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
    // Use polymarket service for storage (both use the same cache)
    return this.polymarketService.storeSelectedToken(marketId, tokenId, outcomeName, marketTitle)
  }

  /**
   * Get all selected tokens
   */
  async getSelectedTokens() {
    return this.polymarketService.getSelectedTokens()
  }

  /**
   * Get cache statistics
   */
  async getCacheStats() {
    return this.polymarketService.getCacheStats()
  }

  /**
   * Get market by ID
   */
  async getMarket(id: string) {
    console.log('🔍 DEBUG MarketSearchService.getMarket called with:', id, 'type:', typeof id)
    
    const result = await this.polymarketService.getMarket(id)
    console.log('🔍 DEBUG MarketSearchService.getMarket result:', result ? 'Found' : 'Not found')
    return result
  }

  /**
   * Clear cache
   */
  async clearCache() {
    return this.polymarketService.clearCache()
  }
}

// Export a default instance
export const marketSearchService = new MarketSearchService()

// Export types for use in other files
export type { SearchConfig } from './types'
export { PolymarketSearchService, KalshiSearchService }