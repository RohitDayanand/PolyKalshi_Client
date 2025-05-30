import fs from 'fs/promises'
import path from 'path'

// Extended market interface to include CLOB data
export interface CachedMarket {
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

// Token ID storage for user selections
export interface SelectedToken {
  marketId: string
  marketTitle: string
  tokenId: string
  outcomeName: string
  selectedAt: string
  platform: 'polymarket' | 'kalshi'
}

// Cache configuration
interface CacheConfig {
  maxMarkets: number
  cacheLifetime: number // in milliseconds
  storageStrategy: 'memory' | 'file' | 'hybrid'
  cacheFilePath?: string
  updateInterval?: number
}

const DEFAULT_CONFIG: CacheConfig = {
  maxMarkets: 300,
  cacheLifetime: 30 * 60 * 1000, // 30 minutes
  storageStrategy: 'memory', // Use memory for browser environment
  cacheFilePath: path.join(process.cwd(), 'cache', 'markets.json'),
  updateInterval: 60 * 1000 // 1 minute for real-time updates
}

/**
 * Market Cache Service
 * Handles caching of market data and token ID storage
 */
export class MarketCacheService {
  private config: CacheConfig
  private memoryCache: Map<string, CachedMarket> = new Map()
  private selectedTokens: Map<string, SelectedToken> = new Map()
  private lastUpdate: number = 0
  private updateTimer?: NodeJS.Timeout

  constructor(config: Partial<CacheConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config }
    this.initializeCache()
  }

  /**
   * Initialize cache and start background updates
   */
  private async initializeCache() {
    // Load existing cache if using file storage
    if (this.config.storageStrategy !== 'memory') {
      await this.loadFromFile()
    }

    // Set up automatic updates
    if (this.config.updateInterval) {
      this.updateTimer = setInterval(() => {
        this.refreshCache()
      }, this.config.updateInterval)
    }
  }

  /**
   * Fetch markets from Polymarket CLOB API
   */
  async fetchPolymarketMarkets(clobApiUrl: string = 'https://clob.polymarket.com'): Promise<CachedMarket[]> {
    try {
      // Fetch active markets from CLOB API
      const response = await fetch(`${clobApiUrl}/markets?active=true&limit=${this.config.maxMarkets}`, {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error(`CLOB API request failed: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      console.log('CLOB API response structure:', Object.keys(data))
      
      // Transform CLOB API response to our format
      return this.transformClobApiResponse(data)
    } catch (error) {
      console.error('Failed to fetch from CLOB API:', error)
      // Fallback to existing market data if available
      return this.loadFallbackData()
    }
  }

  /**
   * Transform CLOB API response to our cached market format
   */
  private transformClobApiResponse(apiData: any): CachedMarket[] {
    const markets: CachedMarket[] = []

    // Handle different possible response structures
    const marketsList = apiData.data || apiData.markets || apiData || []
    
    if (Array.isArray(marketsList)) {
      for (const market of marketsList.slice(0, this.config.maxMarkets)) {
        // Extract token pair (both token IDs)
        const tokenPair = this.extractTokenPair(market)
        
        markets.push({
          id: market.condition_id || market.id || market.ticker,
          title: market.question || market.title || market.description || 'Unknown Market',
          slug: market.slug || market.ticker || market.condition_id,
          category: market.category || market.tags?.[0] || 'General',
          volume: this.parseNumber(market.volume) || this.parseNumber(market.volume_24h) || 0,
          liquidity: this.parseNumber(market.liquidity) || 0,
          active: market.active !== false && market.closed !== true,
          clobTokenIds: tokenPair,
          outcomes: this.extractOutcomes(market),
          lastUpdated: new Date().toISOString(),
          platform: 'polymarket'
        })
      }
    }

    console.log(`Transformed ${markets.length} markets from CLOB API`)
    return markets
  }

  /**
   * Extract token pair from market data
   */
  private extractTokenPair(market: any): string[] {
    // Try different possible structures for token IDs
    if (market.tokens && Array.isArray(market.tokens)) {
      return market.tokens.map((token: any) => token.token_id || token.tokenId || token.id).filter(Boolean)
    }
    
    if (market.clobTokenIds && Array.isArray(market.clobTokenIds)) {
      return market.clobTokenIds
    }
    
    if (market.token_ids && Array.isArray(market.token_ids)) {
      return market.token_ids
    }
    
    // If we have individual token fields
    const tokenIds = []
    if (market.yes_token_id) tokenIds.push(market.yes_token_id)
    if (market.no_token_id) tokenIds.push(market.no_token_id)
    
    return tokenIds
  }

  /**
   * Extract outcomes from market data
   */
  private extractOutcomes(market: any): Array<{name: string, tokenId: string, price: number}> {
    const outcomes = []
    
    if (market.tokens && Array.isArray(market.tokens)) {
      for (const token of market.tokens) {
        outcomes.push({
          name: token.outcome || token.name || 'Unknown',
          tokenId: token.token_id || token.tokenId || token.id,
          price: this.parseNumber(token.price) || 0
        })
      }
    } else {
      // Default binary outcomes for prediction markets
      const tokenPair = this.extractTokenPair(market)
      if (tokenPair.length >= 2) {
        outcomes.push(
          {
            name: 'Yes',
            tokenId: tokenPair[0],
            price: this.parseNumber(market.yes_price) || 0.5
          },
          {
            name: 'No', 
            tokenId: tokenPair[1],
            price: this.parseNumber(market.no_price) || 0.5
          }
        )
      }
    }
    
    return outcomes
  }

  /**
   * Parse number from various formats
   */
  private parseNumber(value: any): number {
    if (typeof value === 'number') return value
    if (typeof value === 'string') {
      const parsed = parseFloat(value)
      return isNaN(parsed) ? 0 : parsed
    }
    return 0
  }

  /**
   * Load fallback data from existing market_data.json
   */
  private async loadFallbackData(): Promise<CachedMarket[]> {
    try {
      const fallbackPath = path.join(process.cwd(), '..', 'poly-starter-code', 'market_data.json')
      const data = await fs.readFile(fallbackPath, 'utf-8')
      const marketData = JSON.parse(data)
      
      // Transform existing data format
      return [{
        id: marketData.id,
        title: marketData.title,
        slug: marketData.slug,
        category: 'Politics', // default category
        volume: marketData.volume || 0,
        liquidity: marketData.liquidity || 0,
        active: marketData.active,
        clobTokenIds: marketData.clobTokenIds || [],
        outcomes: [],
        lastUpdated: new Date().toISOString(),
        platform: 'polymarket'
      }]
    } catch (error) {
      console.error('Failed to load fallback data:', error)
      return []
    }
  }

  /**
   * Update cache with fresh market data
   */
  async refreshCache(clobApiUrl?: string): Promise<void> {
    try {
      const markets = await this.fetchPolymarketMarkets(clobApiUrl || '')
      
      // Update memory cache
      this.memoryCache.clear()
      for (const market of markets) {
        this.memoryCache.set(market.id, market)
      }

      this.lastUpdate = Date.now()

      // Save to file if using file storage
      if (this.config.storageStrategy !== 'memory') {
        await this.saveToFile()
      }

      console.log(`Cache updated with ${markets.length} markets`)
    } catch (error) {
      console.error('Failed to refresh cache:', error)
    }
  }

  /**
   * Search cached markets
   */
  searchMarkets(query: string, maxResults: number = 20): CachedMarket[] {
    const results: CachedMarket[] = []
    const lowercaseQuery = query.toLowerCase()

    for (const market of this.memoryCache.values()) {
      if (results.length >= maxResults) break

      const titleMatch = market.title.toLowerCase().includes(lowercaseQuery)
      const slugMatch = market.slug.toLowerCase().includes(lowercaseQuery)
      const categoryMatch = market.category.toLowerCase().includes(lowercaseQuery)

      if (titleMatch || slugMatch || categoryMatch) {
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
   * Store selected token ID
   */
  storeSelectedToken(
    marketId: string,
    tokenId: string,
    outcomeName: string,
    marketTitle: string
  ): void {
    const selectedToken: SelectedToken = {
      marketId,
      marketTitle,
      tokenId,
      outcomeName,
      selectedAt: new Date().toISOString(),
      platform: 'polymarket'
    }

    this.selectedTokens.set(`${marketId}-${tokenId}`, selectedToken)
    
    // Optionally save to persistent storage
    this.saveSelectedTokens()
  }

  /**
   * Get selected tokens
   */
  getSelectedTokens(): SelectedToken[] {
    return Array.from(this.selectedTokens.values())
  }

  /**
   * Get market by ID
   */
  getMarket(id: string): CachedMarket | undefined {
    return this.memoryCache.get(id)
  }

  /**
   * Get cache statistics
   */
  getCacheStats() {
    return {
      marketCount: this.memoryCache.size,
      selectedTokenCount: this.selectedTokens.size,
      lastUpdate: new Date(this.lastUpdate).toISOString(),
      cacheAge: Date.now() - this.lastUpdate,
      isStale: Date.now() - this.lastUpdate > this.config.cacheLifetime
    }
  }

  /**
   * Save cache to file
   */
  private async saveToFile(): Promise<void> {
    try {
      const cacheDir = path.dirname(this.config.cacheFilePath!)
      await fs.mkdir(cacheDir, { recursive: true })
      
      const cacheData = {
        markets: Array.from(this.memoryCache.values()),
        lastUpdate: this.lastUpdate,
        timestamp: new Date().toISOString()
      }

      await fs.writeFile(this.config.cacheFilePath!, JSON.stringify(cacheData, null, 2))
    } catch (error) {
      console.error('Failed to save cache to file:', error)
    }
  }

  /**
   * Load cache from file
   */
  private async loadFromFile(): Promise<void> {
    try {
      const data = await fs.readFile(this.config.cacheFilePath!, 'utf-8')
      const cacheData = JSON.parse(data)
      
      if (cacheData.markets && Array.isArray(cacheData.markets)) {
        this.memoryCache.clear()
        for (const market of cacheData.markets) {
          this.memoryCache.set(market.id, market)
        }
        this.lastUpdate = cacheData.lastUpdate || 0
      }
    } catch (error) {
      console.log('No existing cache file found, starting fresh')
    }
  }

  /**
   * Save selected tokens to file
   */
  private async saveSelectedTokens(): Promise<void> {
    try {
      const tokensPath = path.join(path.dirname(this.config.cacheFilePath!), 'selected-tokens.json')
      const tokensData = {
        tokens: Array.from(this.selectedTokens.values()),
        timestamp: new Date().toISOString()
      }

      await fs.writeFile(tokensPath, JSON.stringify(tokensData, null, 2))
    } catch (error) {
      console.error('Failed to save selected tokens:', error)
    }
  }

  /**
   * Cleanup resources
   */
  destroy(): void {
    if (this.updateTimer) {
      clearInterval(this.updateTimer)
    }
  }
}

// Singleton instance
export const marketCache = new MarketCacheService()
