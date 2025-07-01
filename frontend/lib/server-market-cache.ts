// Server-compatible market cache for API routes (no localStorage)
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

export interface SelectedToken {
  marketId: string
  marketTitle: string
  tokenId: string
  outcomeName: string
  selectedAt: string
  platform: 'polymarket' | 'kalshi'
}

/**
 * Server Market Cache Service (in-memory only for API routes)
 */
export class ServerMarketCache {
  private memoryCache: Map<string, CachedMarket> = new Map()
  private selectedTokens: Map<string, SelectedToken> = new Map()
  private lastUpdate: number = 0
  private cacheLifetime: number = 30 * 60 * 1000 // 30 minutes

  /**
   * Fetch markets from Polymarket CLOB API with cursor pagination
   */
  async fetchPolymarketMarkets(): Promise<CachedMarket[]> {
    const allMarkets: CachedMarket[] = []
    let nextCursor: string | null = null
    const maxMarkets = 2500 // Half of our 5000 target
    const batchSize = 500 // Polymarket API limit per request
    let offset = 0
    
    try {
      console.log(`🔄 Starting Polymarket pagination (target: ${maxMarkets} markets)`)
      
      while (allMarkets.length < maxMarkets) {
        // Build URL with cursor pagination
        let url = `https://gamma-api.polymarket.com/markets?active=true&closed=false&archived=false&limit=${batchSize}&offset=${offset}`
        if (offset < maxMarkets) {
          offset += batchSize
        }
        
        console.log(`📥 Fetching Polymarket batch ${Math.ceil(allMarkets.length / batchSize) + 1}...`)
        console.log(`🔗 Request URL: ${url}`)
        
        const response = await fetch(url, {
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        })
        
        if (!response.ok) {
          throw new Error(`CLOB API request failed: ${response.status} ${response.statusText}`)
        }

        const data = await response.json()
        
        // Debug: Log the response structure
        console.log('🔍 API Response structure:')
        console.log('- Response keys:', Object.keys(data))
        console.log('- next_cursor value:', data.next_cursor)
        console.log('- next_cursor type:', typeof data.next_cursor)
        console.log('- Raw response sample:', JSON.stringify(data, null, 2).substring(0, 500) + '...')
        
        const batchMarkets = this.transformClobApiResponse(data)
        
        if (batchMarkets.length === 0) {
          console.log('📭 No more Polymarket markets available')
          break
        }
        
        allMarkets.push(...batchMarkets)
        console.log(`✅ Polymarket batch complete: ${batchMarkets.length} markets (total: ${allMarkets.length})`)
        
        // Check for next cursor
        nextCursor = data.next_cursor || null
        console.log('🔗 Offset', offset)

        
        // Small delay to be respectful to the API
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      
      console.log(`🎯 Polymarket fetch complete: ${allMarkets.length} markets cached`)
      return allMarkets.slice(0, maxMarkets) // Ensure we don't exceed target
      
    } catch (error) {
      console.error('Failed to fetch from CLOB API:', error)
      return allMarkets // Return whatever we managed to fetch
    }
  }

  /**
   * Transform CLOB API response to our cached market format
   */
  private transformClobApiResponse(apiData: any): CachedMarket[] {
    const markets: CachedMarket[] = []
    const marketsList = apiData.data || apiData.markets || apiData || []
    
    if (Array.isArray(marketsList)) {
      for (const market of marketsList) {
        const tokenPair = this.extractTokenPair(market)
        
        markets.push({
          id: market.condition_id || market.id || market.ticker || `market_${Date.now()}_${markets.length}`,
          title: market.question || market.title || market.description || 'Unknown Market',
          slug: market.market_slug || market.slug || market.ticker || market.condition_id || market.id || '',
          category: market.category || market.tags?.[market.tags.length - 1] || 'General',
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
      return market.tokens.map((token: any) => token.token_id).filter(Boolean)
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
          tokenId: token.token_id,
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
      const polymarketMarkets = await this.fetchPolymarketMarkets()
      const kalshiMarkets = await this.fetchKalshiMarkets()
      
      // Update memory cache
      this.memoryCache.clear()
      for (const market of [...polymarketMarkets, ...kalshiMarkets]) {
        this.memoryCache.set(market.id, market)
      }

      this.lastUpdate = Date.now()
      console.log(`Server cache updated with ${polymarketMarkets.length + kalshiMarkets.length} markets`)
    } catch (error) {
      console.error('Failed to refresh server cache:', error)
    }
  }

  /**
   * Fetch markets from Kalshi API with cursor pagination
   */
  async fetchKalshiMarkets(): Promise<CachedMarket[]> {
    const allMarkets: CachedMarket[] = []
    let cursor: string | null = null
    const maxMarkets = 5000 // Increased from 2500 to get more markets
    const batchSize = 200 // Reduced from 500 to be more conservative and get faster responses
    
    try {
      console.log(`🔄 Starting Kalshi pagination (target: ${maxMarkets} markets)`)
      
      while (allMarkets.length < maxMarkets) {
        // Build URL with improved filtering for active markets
        let url = `https://api.elections.kalshi.com/trade-api/v2/markets?limit=${batchSize}`
        
        // Add status filter - get open markets and those that can still be traded
        url += `&status=open`
        
        // Add date filters to exclude markets that are about to close or have closed
        const nowTimestamp = Math.floor(Date.now() / 1000) // Current time as pure integer (Unix timestamp)
        url += `&min_close_ts=${nowTimestamp}` // Only markets closing after current time
        
        // Add cursor for pagination
        if (cursor) {
          url += `&cursor=${encodeURIComponent(cursor)}`
        }
        
        console.log(`📥 Fetching Kalshi batch ${Math.ceil(allMarkets.length / batchSize) + 1}...`)
        console.log(`🔗 Request URL: ${url}`)
        
        const response = await fetch(url, {
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        })
        
        if (!response.ok) {
          throw new Error(`Kalshi API request failed: ${response.status} ${response.statusText}`)
        }

        const data = await response.json()
        
        // Debug: Log the response structure
        console.log('🔍 Kalshi API Response structure:')
        console.log('- Response keys:', Object.keys(data))
        console.log('- cursor value:', data.cursor)
        console.log('- cursor type:', typeof data.cursor)
        console.log('- Raw response sample:', JSON.stringify(data, null, 2).substring(0, 500) + '...')
        
        const batchMarkets = this.transformKalshiApiResponse(data)
        
        if (batchMarkets.length === 0) {
          console.log('📭 No more Kalshi markets available')
          break
        }
        
        allMarkets.push(...batchMarkets)
        console.log(`✅ Kalshi batch complete: ${batchMarkets.length} markets (total: ${allMarkets.length})`)
        
        // Check for next cursor
        cursor = data.cursor || null
        console.log('🔗 Next cursor extracted:', cursor)
        
     
        if (!cursor) {
          console.log('🏁 Reached end of Kalshi pagination')
          break
        }
        
        // Small delay to be respectful to the API
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      
      console.log(`🎯 Kalshi fetch complete: ${allMarkets.length} markets cached`)
      return allMarkets.slice(0, maxMarkets) // Ensure we don't exceed target
      
    } catch (error) {
      console.error('Failed to fetch from Kalshi API:', error)
      return allMarkets // Return whatever we managed to fetch
    }
  }

  /**
   * Transform Kalshi API response to our cached market format
   */
  private transformKalshiApiResponse(apiData: any): CachedMarket[] {
    console.log('🔍 DEBUG: Sample Kalshi market data:', apiData.markets?.[0])
    console.log('🔍 DEBUG: Available fields:', apiData.markets?.[0] ? Object.keys(apiData.markets[0]) : 'No markets')
    
    const markets: CachedMarket[] = []
    const marketsList = apiData.markets || apiData.data || apiData || []
    
    if (Array.isArray(marketsList)) {
      for (const market of marketsList) {
        markets.push({
          id: market.ticker || market.id || `kalshi_${Date.now()}_${markets.length}`,
          title: market.title || market.subtitle || market.ticker || 'Unknown Market',
          slug: market.ticker || market.slug || '',
          category: this.extractKalshiCategory(market),
          volume: this.parseNumber(market.volume) || this.parseNumber(market.dollar_volume) || 0,
          liquidity: this.parseNumber(market.liquidity) || this.parseNumber(market.open_interest) || 0,
          active: market.status === 'open' || market.can_close_early === false,
          clobTokenIds: this.extractKalshiTokenIds(market),
          outcomes: this.extractKalshiOutcomes(market),
          lastUpdated: new Date().toISOString(),
          platform: 'kalshi'
        })
        
        // Debug volume calculation for first few markets
        if (markets.length <= 3) {
          console.log(`🔍 DEBUG: Market "${market.title || market.ticker}"`)
          console.log(`  - market.volume: ${market.volume}`)
          console.log(`  - market.dollar_volume: ${market.dollar_volume}`)
          console.log(`  - Final volume: ${this.parseNumber(market.volume) || this.parseNumber(market.dollar_volume) || 0}`)
        }
      }
    }

    return markets
  }

  /**
   * Extract category from Kalshi market data
   */
  private extractKalshiCategory(market: any): string {
    // Kalshi uses event_ticker for categorization
    if (market.event_ticker) {
      return market.event_ticker.replace(/-/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())
    }
    
    if (market.series_ticker) {
      return market.series_ticker.replace(/-/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())
    }
    
    if (market.category) return market.category
    
    return 'Politics'
  }

  /**
   * Extract token IDs from Kalshi market data
   */
  private extractKalshiTokenIds(market: any): string[] {
    const tokenIds = []
    
    // Kalshi typically has yes/no tokens
    if (market.yes_sub_id) tokenIds.push(market.yes_sub_id)
    if (market.no_sub_id) tokenIds.push(market.no_sub_id)
    
    // Fallback to ticker-based IDs
    if (tokenIds.length === 0 && market.ticker) {
      tokenIds.push(`${market.ticker}_YES`, `${market.ticker}_NO`)
    }
    
    return tokenIds
  }

  /**
   * Extract outcomes from Kalshi market data
   */
  private extractKalshiOutcomes(market: any): Array<{name: string, tokenId: string, price: number}> {
    const outcomes = []
    
    // Extract yes/no prices
    const yesPrice = this.parseNumber(market.yes_bid) || this.parseNumber(market.yes_ask) || 0.5
    const noPrice = this.parseNumber(market.no_bid) || this.parseNumber(market.no_ask) || (1 - yesPrice)
    
    const tokenIds = this.extractKalshiTokenIds(market)
    
    if (tokenIds.length >= 2) {
      outcomes.push(
        {
          name: 'Yes',
          tokenId: tokenIds[0],
          price: yesPrice
        },
        {
          name: 'No',
          tokenId: tokenIds[1], 
          price: noPrice
        }
      )
    }
    
    return outcomes
  }

  /**
   * Search cached markets
   */
  searchMarkets(query: string, maxResults: number = 50): CachedMarket[] {
    const results: CachedMarket[] = []
    const lowercaseQuery = query.toLowerCase()

    // Count markets by platform for debugging
    let polymarketCount = 0
    let kalshiCount = 0
    for (const market of this.memoryCache.values()) {
      if (market.platform === 'polymarket') polymarketCount++
      if (market.platform === 'kalshi') kalshiCount++
    }

    console.log(`🔍 Searching for "${query}" in ${this.memoryCache.size} cached markets (${polymarketCount} Polymarket, ${kalshiCount} Kalshi)`)

    for (const market of this.memoryCache.values()) {
      if (results.length >= maxResults) break

      const titleMatch = market.title?.toLowerCase().includes(lowercaseQuery) || false
      const slugMatch = market.slug?.toLowerCase().includes(lowercaseQuery) || false

      if (titleMatch || slugMatch) {
        console.log(`✅ Found match [${market.platform.toUpperCase()}]: "${market.title}"`)
        results.push(market)
      }
    }

    // Count results by platform
    const polymarketResults = results.filter(m => m.platform === 'polymarket').length
    const kalshiResults = results.filter(m => m.platform === 'kalshi').length
    console.log(`🎯 Search completed: ${results.length} total results (${polymarketResults} Polymarket, ${kalshiResults} Kalshi)`)

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
   * Search cached markets filtered by platform
   */
  searchMarketsByPlatform(query: string, platform: 'polymarket' | 'kalshi', maxResults: number = 50): CachedMarket[] {
    const results: CachedMarket[] = []
    const lowercaseQuery = query.toLowerCase()

    // Count markets by platform for debugging
    let platformCount = 0
    for (const market of this.memoryCache.values()) {
      if (market.platform === platform) platformCount++
    }

    console.log(`🔍 Searching for "${query}" in ${platformCount} ${platform.toUpperCase()} markets only`)

    for (const market of this.memoryCache.values()) {
      // Skip markets from other platforms
      if (market.platform !== platform) continue
      
      if (results.length >= maxResults) break

      const titleMatch = market.title?.toLowerCase().includes(lowercaseQuery) || false
      const slugMatch = market.slug?.toLowerCase().includes(lowercaseQuery) || false

      if (titleMatch || slugMatch) {
        console.log(`✅ Found ${platform.toUpperCase()} match: "${market.title}"`)
        results.push(market)
      }
    }

    console.log(`🎯 ${platform.toUpperCase()} search completed: ${results.length} results found`)

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
   * Store selected token ID (stores both tokens from the pair)
   */
  storeSelectedToken(
    marketId: string,
    selectedTokenId: string,
    outcomeName: string,
    marketTitle: string
  ): void {
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

      this.selectedTokens.set(`${marketId}-${tokenId}`, selectedToken)
    }

    console.log(`Stored token pair for market ${marketId}:`, tokenPair)
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
    console.log('Server cache cleared')
  }
}

// Singleton instance for server use
export const serverMarketCache = new ServerMarketCache()
