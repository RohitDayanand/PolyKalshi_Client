// Browser-compatible market cache using localStorage
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

// Cache configuration for browser environment
interface BrowserCacheConfig {
  maxMarkets: number
  cacheLifetime: number // in milliseconds
  updateInterval: number
  storageKeys: {
    markets: string
    selectedTokens: string
    lastUpdate: string
  }
}

const DEFAULT_BROWSER_CONFIG: BrowserCacheConfig = {
  maxMarkets: 300,
  cacheLifetime: 30 * 60 * 1000, // 30 minutes
  updateInterval: 60 * 1000, // 1 minute
  storageKeys: {
    markets: 'polymarket_cached_markets',
    selectedTokens: 'polymarket_selected_tokens', 
    lastUpdate: 'polymarket_cache_last_update'
  }
}

/**
 * Browser Market Cache Service using localStorage
 */
export class BrowserMarketCache {
  private config: BrowserCacheConfig
  private updateTimer?: number

  constructor(config: Partial<BrowserCacheConfig> = {}) {
    this.config = { ...DEFAULT_BROWSER_CONFIG, ...config }
    this.initializeCache()
  }

  /**
   * Initialize cache and start background updates
   */
  private initializeCache() {
    // Load cache on first browser start, but don't set up automatic polling
    this.refreshCacheOnFirstLoad()
    
    // Automatic updates DISABLED to prevent polling
    // this.updateTimer = window.setInterval(() => {
    //   this.refreshCache()
    // }, this.config.updateInterval)
  }

  /**
   * Refresh cache only if it's empty or very stale (first load)
   */
  private async refreshCacheOnFirstLoad() {
    try {
      const stats = this.getCacheStats()
      
      // Only refresh if cache is empty or very old (first browser start)
      if (stats.marketCount === 0 || stats.cacheAge > 2 * 60 * 60 * 1000) { // 2 hours
        console.log('🚀 First load: refreshing cache...')
        await this.refreshCache()
      } else {
        console.log('📋 Using existing cached data')
      }
    } catch (error) {
      console.error('Failed to check cache on first load:', error)
    }
  }

  /**
   * Fetch markets from our API route (which proxies to Polymarket CLOB API)
   */
  async fetchPolymarketMarkets(): Promise<CachedMarket[]> {
    try {
      const response = await fetch('/api/markets', {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error(`Markets API request failed: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      
      if (!data.success) {
        throw new Error(data.error || 'API request failed')
      }
      
      return data.markets || []
    } catch (error) {
      console.error('Failed to fetch from markets API:', error)
      return []
    }
  }

  /**
   * Transform CLOB API response to our cached market format
   */
  private transformClobApiResponse(apiData: any): CachedMarket[] {
    const markets: CachedMarket[] = []
    const marketsList = apiData.data || apiData.markets || apiData || []
    
    if (Array.isArray(marketsList)) {
      for (const market of marketsList.slice(0, this.config.maxMarkets)) {
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

    return markets
  }

  /**
   * Extract token pair from market data
   */
  private extractTokenPair(market: any): string[] {
    if (market.tokens && Array.isArray(market.tokens)) {
      return market.tokens.map((token: any) => token.token_id || token.tokenId || token.id).filter(Boolean)
    }
    
    if (market.clobTokenIds && Array.isArray(market.clobTokenIds)) {
      return market.clobTokenIds
    }
    
    if (market.token_ids && Array.isArray(market.token_ids)) {
      return market.token_ids
    }
    
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
   * Update cache with fresh market data
   */
  async refreshCache(): Promise<void> {
    try {
      const markets = await this.fetchPolymarketMarkets()
      
      // Save to localStorage
      localStorage.setItem(this.config.storageKeys.markets, JSON.stringify(markets))
      localStorage.setItem(this.config.storageKeys.lastUpdate, Date.now().toString())

      console.log(`Browser cache updated with ${markets.length} markets`)
    } catch (error) {
      console.error('Failed to refresh browser cache:', error)
    }
  }

  /**
   * Search cached markets
   */
  searchMarkets(query: string, maxResults: number = 20): CachedMarket[] {
    const marketsJson = localStorage.getItem(this.config.storageKeys.markets)
    if (!marketsJson) return []

    try {
      const markets: CachedMarket[] = JSON.parse(marketsJson)
      const results: CachedMarket[] = []
      const lowercaseQuery = query.toLowerCase()

      for (const market of markets) {
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
    } catch (error) {
      console.error('Failed to parse cached markets:', error)
      return []
    }
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
    try {
      const existingTokensJson = localStorage.getItem(this.config.storageKeys.selectedTokens)
      const existingTokens: SelectedToken[] = existingTokensJson ? JSON.parse(existingTokensJson) : []

      // Get the full market to access token pair
      const market = this.getMarket(marketId)
      if (!market) {
        console.warn('Market not found for token storage:', marketId)
        return
      }

      // Store both tokens from the pair
      const tokenPair = market.clobTokenIds || []
      for (const tokenId of tokenPair) {
        const isSelected = tokenId === selectedTokenId
        const outcome = market.outcomes?.find(o => o.tokenId === tokenId)
        
        const selectedToken: SelectedToken = {
          marketId,
          marketTitle,
          tokenId,
          outcomeName: outcome?.name || (isSelected ? outcomeName : 'Other'),
          selectedAt: new Date().toISOString(),
          platform: 'polymarket'
        }

        // Remove existing entry for this token if it exists
        const filteredTokens = existingTokens.filter(t => t.tokenId !== tokenId)
        filteredTokens.push(selectedToken)
        
        localStorage.setItem(this.config.storageKeys.selectedTokens, JSON.stringify(filteredTokens))
      }

      console.log(`Stored token pair for market ${marketId}:`, tokenPair)
    } catch (error) {
      console.error('Failed to store selected tokens:', error)
    }
  }

  /**
   * Get selected tokens
   */
  getSelectedTokens(): SelectedToken[] {
    try {
      const tokensJson = localStorage.getItem(this.config.storageKeys.selectedTokens)
      return tokensJson ? JSON.parse(tokensJson) : []
    } catch (error) {
      console.error('Failed to get selected tokens:', error)
      return []
    }
  }

  /**
   * Get market by ID
   */
  getMarket(id: string): CachedMarket | undefined {
    try {
      const marketsJson = localStorage.getItem(this.config.storageKeys.markets)
      if (!marketsJson) return undefined

      const markets: CachedMarket[] = JSON.parse(marketsJson)
      return markets.find(market => market.id === id)
    } catch (error) {
      console.error('Failed to get market:', error)
      return undefined
    }
  }

  /**
   * Get cache statistics
   */
  getCacheStats() {
    try {
      const marketsJson = localStorage.getItem(this.config.storageKeys.markets)
      const tokensJson = localStorage.getItem(this.config.storageKeys.selectedTokens)
      const lastUpdateStr = localStorage.getItem(this.config.storageKeys.lastUpdate)

      const marketCount = marketsJson ? JSON.parse(marketsJson).length : 0
      const selectedTokenCount = tokensJson ? JSON.parse(tokensJson).length : 0
      const lastUpdate = lastUpdateStr ? parseInt(lastUpdateStr) : 0

      return {
        marketCount,
        selectedTokenCount,
        lastUpdate: new Date(lastUpdate).toISOString(),
        cacheAge: Date.now() - lastUpdate,
        isStale: Date.now() - lastUpdate > this.config.cacheLifetime
      }
    } catch (error) {
      console.error('Failed to get cache stats:', error)
      return {
        marketCount: 0,
        selectedTokenCount: 0,
        lastUpdate: new Date().toISOString(),
        cacheAge: 0,
        isStale: true
      }
    }
  }

  /**
   * Clear all cached data
   */
  clearCache(): void {
    localStorage.removeItem(this.config.storageKeys.markets)
    localStorage.removeItem(this.config.storageKeys.selectedTokens)
    localStorage.removeItem(this.config.storageKeys.lastUpdate)
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

// Singleton instance for browser use
export const browserMarketCache = new BrowserMarketCache()
