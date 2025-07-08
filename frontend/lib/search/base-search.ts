import type { Market } from '@/types/market'
import type { CachedMarket, SearchConfig } from './types'
import { defaultConfig } from './types'

// Import cache at module level
import { serverMarketCache } from '../server-market-cache'

// Always use server cache (no browser cache needed)
async function getMarketCache() {
    return serverMarketCache
}

/**
 * Base search service class with common functionality
 */
export abstract class BaseSearchService {
  protected config: SearchConfig

  constructor(config: Partial<SearchConfig> = {}) {
    this.config = { ...defaultConfig, ...config }
  }

  /**
   * Abstract method to be implemented by platform-specific services
   */
  abstract searchQuestions(query: string): Promise<Market[]>
  abstract generateQuestions(query: string): Promise<Market[]>

  /**
   * Common method to get market cache
   */
  protected async getMarketCache() {
    return getMarketCache()
  }

  /**
   * Filter and rank results based on relevance and business logic
   */
  protected filterAndRankResults(markets: Market[], query: string): Market[] {
    // Apply volume threshold filter
    let filtered = markets.filter(market => {
      const passesVolumeFilter = !this.config.minVolumeThreshold || market.volume >= 0
      return passesVolumeFilter
    })

    if (this.config.enableFuzzySearch) {
      // Simple relevance scoring based on query match
      filtered = filtered.map(market => ({
        ...market,
        relevanceScore: this.calculateRelevanceScore(market.title, query)
      }))

      // Sort by relevance score
      filtered.sort((a, b) => (b as any).relevanceScore - (a as any).relevanceScore)
    }

    // Remove relevance score from final results
    return filtered.map(({ ...market }) => {
      delete (market as any).relevanceScore
      return market
    }).slice(0, this.config.maxResults)
  }

  /**
   * Calculate relevance score for ranking
   */
  protected calculateRelevanceScore(title: string, query: string): number {
    const titleLower = title.toLowerCase()
    const queryLower = query.toLowerCase()
    
    // Exact match gets highest score
    if (titleLower.includes(queryLower)) {
      return 100
    }

    // Word-by-word matching
    const queryWords = queryLower.split(' ')
    const titleWords = titleLower.split(' ')
    
    let matchCount = 0
    for (const queryWord of queryWords) {
      for (const titleWord of titleWords) {
        if (titleWord.includes(queryWord) || queryWord.includes(titleWord)) {
          matchCount++
          break
        }
      }
    }

    return (matchCount / queryWords.length) * 50
  }

  /**
   * Transform cached market to Market interface
   */
  protected transformCachedMarketToMarket(cachedMarket: CachedMarket): Market {
    // Add backend tracking fields for both platforms
    const transformed = {
      id: cachedMarket.id,
      title: cachedMarket.title,
      category: cachedMarket.category,
      volume: cachedMarket.volume,
      liquidity: cachedMarket.liquidity,
      price: cachedMarket.outcomes?.[0]?.price,
      platform: cachedMarket.platform,
      lastUpdated: cachedMarket.lastUpdated,
      // Backend tracking fields:
      tokenIds: cachedMarket.platform === 'polymarket' ? cachedMarket.clobTokenIds : undefined,
      kalshiTicker: cachedMarket.platform === 'kalshi' ? cachedMarket.id : undefined
    }
    
    return transformed
  }

  /**
   * Helper methods for generating mock data
   */
  protected generateRandomVolume(): number {
    const min = this.config.minVolumeThreshold || 1000
    return Math.floor(Math.random() * 1000000) + min
  }

  protected generateRandomLiquidity(): number {
    return Math.floor(Math.random() * 100000) + 5000
  }

  /**
   * Update search configuration
   */
  updateConfig(newConfig: Partial<SearchConfig>): void {
    this.config = { ...this.config, ...newConfig }
  }

  /**
   * Get current search configuration
   */
  getConfig(): SearchConfig {
    return { ...this.config }
  }

  /**
   * Store selected token ID when user clicks on a market (stores both tokens from pair)
   */
  async storeSelectedToken(marketId: string, tokenId: string, outcomeName: string, marketTitle: string): Promise<void> {
    const cache = await this.getMarketCache()
    cache.storeSelectedToken(marketId, tokenId, outcomeName, marketTitle)
  }

  /**
   * Get all selected tokens
   */
  async getSelectedTokens() {
    const cache = await this.getMarketCache()
    return cache.getSelectedTokens()
  }

  /**
   * Get cache statistics
   */
  async getCacheStats() {
    const cache = await this.getMarketCache()
    return cache.getCacheStats()
  }

  /**
   * Get market by ID
   */
  async getMarket(id: string) {
    const cache = await this.getMarketCache()
    return cache.getMarket(id)
  }

  /**
   * Clear cache
   */
  async clearCache() {
    const cache = await this.getMarketCache()
    return cache.clearCache()
  }
}