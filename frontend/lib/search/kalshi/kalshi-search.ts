import type { Market } from '@/types/market'
import type { CachedMarket, SearchConfig } from '../types'
import { BaseSearchService } from '../base-search'

/**
 * Kalshi-specific search service
 */
export class KalshiSearchService extends BaseSearchService {
  constructor(config: Partial<SearchConfig> = {}) {
    super(config)
  }

  /**
   * Search Kalshi questions based on custom logic
   */
  async searchQuestions(query: string): Promise<Market[]> {
    try {
      const cache = await this.getMarketCache()
      
      // Check if cache needs refresh - Only on first load when empty
      const cacheStats = cache.getCacheStats()
      
      if (cacheStats.marketCount === 0) {
        await cache.refreshCache()
      }

      // Search cached markets - Kalshi only
      const kalshiResults = cache.searchMarketsByPlatform 
        ? cache.searchMarketsByPlatform(query, 'kalshi', this.config.maxResults)
        : cache.searchMarkets(query, this.config.maxResults * 2).filter((market: CachedMarket) => market.platform === 'kalshi')
      
      // If we have cached results, use them
      if (kalshiResults.length > 0) {
        // Convert to Market interface format
        const markets: Market[] = kalshiResults.slice(0, this.config.maxResults).map((cachedMarket: CachedMarket) => this.transformCachedMarketToMarket(cachedMarket))
        
        const filteredResults = this.filterAndRankResults(markets, query)
        
        return filteredResults
      } else {
        return []
      }
    } catch (error) {
      console.error('❌ Error searching Kalshi questions:', error)
      console.error('❌ Stack trace:', (error as Error)?.stack)
      // Fallback to generated questions if cache fails
      const questions = await this.generateQuestions(query)
      return this.filterAndRankResults(questions, query)
    }
  }

  /**
   * Generate Kalshi questions based on query
   */
  async generateQuestions(query: string): Promise<Market[]> {
    // Example implementation - replace with your actual logic
    const questionTemplates = [
      `Will ${query} occur within the next quarter?`,
      `${query}: Probability of success`,
      `Will ${query} exceed expectations this year?`,
      `${query} market forecast - binary outcome`,
      `Will there be a ${query} announcement in 2025?`
    ]

    const results: Market[] = []

    for (let i = 0; i < Math.min(questionTemplates.length, this.config.maxResults); i++) {
      const template = questionTemplates[i]
      
      results.push({
        id: `kalshi_${Date.now()}_${i}`,
        title: template,
        category: 'General',
        volume: this.generateRandomVolume(),
        liquidity: this.generateRandomLiquidity(),
        platform: 'kalshi'
      })
    }

    return results
  }
}