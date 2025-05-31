import type { Market } from '@/types/market'

// Type definitions
interface CachedMarket {
  id: string
  title: string
  slug: string
  category: string
  volume: number
  liquidity: number
  active: boolean
  clobTokenIds?: string[]
  outcomes?: Array<{
    name: string
    tokenId: string
    price: number
  }>
  lastUpdated: string
  platform: 'polymarket' | 'kalshi'
}

// Import caches at module level
import { serverMarketCache } from './server-market-cache'

// Lazy import for browser cache to avoid server-side issues
let browserCachePromise: Promise<any> | null = null

async function getBrowserCache() {
  if (!browserCachePromise) {
    browserCachePromise = import('./browser-market-cache').then(module => module.browserMarketCache)
  }
  return browserCachePromise
}

// Check if we're in browser environment and get the appropriate cache
async function getMarketCache() {
  if (typeof window !== 'undefined') {
    // Browser environment
    return await getBrowserCache()
  } else {
    // Server environment
    return serverMarketCache
  }
}

// Custom search configuration
interface SearchConfig {
  maxResults: number
  enableFuzzySearch: boolean
  minVolumeThreshold?: number
  clobApiUrl?: string
}

const defaultConfig: SearchConfig = {
  maxResults: 50, // Increased from 20 to capture more diverse results
  enableFuzzySearch: true,
  minVolumeThreshold: 1000,
  clobApiUrl: 'https://clob.polymarket.com'
}

/**
 * Main search service class
 */
export class MarketSearchService {
  private config: SearchConfig

  constructor(config: Partial<SearchConfig> = {}) {
    this.config = { ...defaultConfig, ...config }
  }

  /**
   * Search Polymarket questions based on your custom logic
   */
  async searchPolymarketQuestions(query: string): Promise<Market[]> {
    try {
      console.log(`🔍 Starting search for "${query}"`)
      const cache = await getMarketCache()
      console.log('✅ Got cache instance')
      
      // Check if cache needs refresh - Only on first load when empty
      const cacheStats = cache.getCacheStats()
      console.log('📊 Cache stats:', cacheStats)
      
      if (cacheStats.marketCount === 0) {
        console.log('🔄 First load: Refreshing empty cache...')
        await cache.refreshCache()
      } else {
        console.log('📋 Using existing cached data - no automatic refresh')
      }

      // Search cached markets - Polymarket only
      console.log(`🔎 Searching Polymarket markets specifically for "${query}"`)
      const polymarketResults = cache.searchMarketsByPlatform 
        ? cache.searchMarketsByPlatform(query, 'polymarket', this.config.maxResults)
        : cache.searchMarkets(query, this.config.maxResults * 2).filter((market: CachedMarket) => market.platform === 'polymarket')
      console.log(`✅ Found ${polymarketResults.length} Polymarket results`)
      
      // If we have cached results, use them
      if (polymarketResults.length > 0) {
        // Convert to Market interface format
        console.log('🔄 Transforming cached Polymarket markets to Market interface')
        const markets: Market[] = polymarketResults.slice(0, this.config.maxResults).map((cachedMarket: CachedMarket) => this.transformCachedMarketToMarket(cachedMarket))
        console.log(`✅ Transformed ${markets.length} Polymarket markets`)
        
        const filteredResults = this.filterAndRankResults(markets, query)
        console.log(`✅ Final Polymarket result: ${filteredResults.length} markets`)
        
        return filteredResults
      } else {
        console.log('⚠️ No cached Polymarket results found, returning empty array')
        return []
      }
    } catch (error) {
      console.error('❌ Error searching Polymarket questions:', error)
      console.error('❌ Stack trace:', (error as Error)?.stack)
      // Fallback to generated questions if cache fails
      console.log('🔄 Falling back to generated questions')
      const questions = await this.generatePolymarketQuestions(query)
      return this.filterAndRankResults(questions, query)
    }
  }

  /**
   * Search Kalshi questions based on your custom logic
   */
  async searchKalshiQuestions(query: string): Promise<Market[]> {
    try {
      console.log(`🔍 Starting Kalshi search for "${query}"`)
      const cache = await getMarketCache()
      console.log('✅ Got cache instance')
      
      // Check if cache needs refresh - Only on first load when empty
      const cacheStats = cache.getCacheStats()
      console.log('📊 Cache stats:', cacheStats)
      
      if (cacheStats.marketCount === 0) {
        console.log('🔄 First load: Refreshing empty cache...')
        await cache.refreshCache()
      } else {
        console.log('📋 Using existing cached data - no automatic refresh')
      }

      // Search cached markets - Kalshi only
      console.log(`🔎 Searching Kalshi markets specifically for "${query}"`)
      const kalshiResults = cache.searchMarketsByPlatform 
        ? cache.searchMarketsByPlatform(query, 'kalshi', this.config.maxResults)
        : cache.searchMarkets(query, this.config.maxResults * 2).filter((market: CachedMarket) => market.platform === 'kalshi')
      console.log(`✅ Found ${kalshiResults.length} Kalshi results`)
      
      // If we have cached results, use them
      if (kalshiResults.length > 0) {
        // Convert to Market interface format
        console.log('🔄 Transforming cached Kalshi markets to Market interface')
        const markets: Market[] = kalshiResults.slice(0, this.config.maxResults).map((cachedMarket: CachedMarket) => this.transformCachedMarketToMarket(cachedMarket))
        console.log(`✅ Transformed ${markets.length} Kalshi markets`)
        
        const filteredResults = this.filterAndRankResults(markets, query)
        console.log(`✅ Final Kalshi result: ${filteredResults.length} markets`)
        
        return filteredResults
      } else {
        console.log('⚠️ No cached Kalshi results found, returning empty array')
        return []
      }
    } catch (error) {
      console.error('❌ Error searching Kalshi questions:', error)
      console.error('❌ Stack trace:', (error as Error)?.stack)
      // Fallback to generated questions if cache fails
      console.log('🔄 Falling back to generated Kalshi questions')
      const questions = await this.generateKalshiQuestions(query)
      return this.filterAndRankResults(questions, query)
    }
  }

  /**
   * Generate Polymarket questions based on query
   * CUSTOMIZE THIS METHOD with your logic
   */
  private async generatePolymarketQuestions(query: string): Promise<Market[]> {
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
        category: 'General', // Default category since categories are removed
        volume: this.generateRandomVolume(),
        price: Math.random(),
        platform: 'polymarket'
      })
    }

    return results
  }

  /**
   * Generate Kalshi questions based on query
   * CUSTOMIZE THIS METHOD with your logic
   */
  private async generateKalshiQuestions(query: string): Promise<Market[]> {
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
        category: 'General', // Default category since categories are removed
        volume: this.generateRandomVolume(),
        liquidity: this.generateRandomLiquidity(),
        platform: 'kalshi'
      })
    }

    return results
  }

  /**
   * Filter and rank results based on relevance and your business logic
   * CUSTOMIZE THIS METHOD with your ranking algorithm
   */
  private filterAndRankResults(markets: Market[], query: string): Market[] {
    // Apply volume threshold filter
    let filtered = markets.filter(market => 
      !this.config.minVolumeThreshold || market.volume >= this.config.minVolumeThreshold
    )

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
   * CUSTOMIZE THIS METHOD with your ranking algorithm
   */
  private calculateRelevanceScore(title: string, query: string): number {
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
  private transformCachedMarketToMarket(cachedMarket: CachedMarket): Market {
    return {
      id: cachedMarket.id,
      title: cachedMarket.title,
      category: cachedMarket.category,
      volume: cachedMarket.volume,
      liquidity: cachedMarket.liquidity,
      price: cachedMarket.outcomes?.[0]?.price,
      platform: cachedMarket.platform
    }
  }

  /**
   * Helper methods for generating mock data
   * Replace these with actual API calls
   */
  private generateRandomVolume(): number {
    const min = this.config.minVolumeThreshold || 1000
    return Math.floor(Math.random() * 1000000) + min
  }

  private generateRandomLiquidity(): number {
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
    const cache = await getMarketCache()
    cache.storeSelectedToken(marketId, tokenId, outcomeName, marketTitle)
  }

  /**
   * Get all selected tokens
   */
  async getSelectedTokens() {
    const cache = await getMarketCache()
    return cache.getSelectedTokens()
  }

  /**
   * Get cache statistics
   */
  async getCacheStats() {
    const cache = await getMarketCache()
    return cache.getCacheStats()
  }

  /**
   * Get market by ID
   */
  async getMarket(id: string) {
    const cache = await getMarketCache()
    return cache.getMarket(id)
  }

  /**
   * Clear cache
   */
  async clearCache() {
    const cache = await getMarketCache()
    return cache.clearCache()
  }
}

// Export a default instance
export const marketSearchService = new MarketSearchService()

// Export types for use in other files
export type { SearchConfig }
