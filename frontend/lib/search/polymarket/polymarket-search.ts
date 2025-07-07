import type { Market } from '@/types/market'
import type { CachedMarket, SearchConfig } from '../types'
import { BaseSearchService } from '../base-search'

/**
 * Polymarket-specific search service
 */
export class PolymarketSearchService extends BaseSearchService {
  constructor(config: Partial<SearchConfig> = {}) {
    super(config)
  }

  /**
   * Search Polymarket questions based on custom logic
   */
  async searchQuestions(query: string): Promise<Market[]> {
    try {
      const cache = await this.getMarketCache()
      
      // Check if cache needs refresh - Only on first load when empty
      const cacheStats = cache.getCacheStats()
      
      console.log("Retrieval of cache is fine here", cacheStats)

      if (cacheStats.marketCount === 0) {
        await cache.refreshCache()
      }

      // Search cached markets - Polymarket only
      const polymarketResults = cache.searchMarketsByPlatform 
        ? cache.searchMarketsByPlatform(query, 'polymarket', this.config.maxResults)
        : cache.searchMarkets(query, this.config.maxResults * 2).filter((market: CachedMarket) => market.platform === 'polymarket')
      
      // If we have cached results, use them
      if (polymarketResults.length > 0) {
        // Convert to Market interface format
        const markets: Market[] = polymarketResults.slice(0, this.config.maxResults).map((cachedMarket: CachedMarket) => this.transformCachedMarketToMarket(cachedMarket))
        
        const filteredResults = this.filterAndRankResults(markets, query)
        
        return filteredResults
      } else {
        return []
      }
    } catch (error) {
      console.error('❌ Error searching Polymarket questions:', error)
      console.error('❌ Stack trace:', (error as Error)?.stack)
      // Fallback to generated questions if cache fails
      const questions = await this.generateQuestions(query)
      return this.filterAndRankResults(questions, query)
    }
  }

  /**
   * Generate Polymarket questions based on query
   */
  async generateQuestions(query: string): Promise<Market[]> {
    // Example implementation - replace with your actual logic
    const questionTemplates = [
      `Will ${query} happen before the end of 2025?`,
      `Will ${query} reach a new milestone this year?`,
      `${query}: What will be the outcome?`,
      `Will there be significant news about ${query} in the next 6 months?`,
      `${query} prediction market - which scenario is most likely?`
    ]

    const results: Market[] = []

    for (let i = 0; i < Math.min(questionTemplates.length, this.config.maxResults); i++) {
      const template = questionTemplates[i]
      
      results.push({
        id: `poly_${Date.now()}_${i}`,
        title: template,
        category: 'General',
        volume: this.generateRandomVolume(),
        price: Math.random(),
        platform: 'polymarket'
      })
    }

    return results
  }
}