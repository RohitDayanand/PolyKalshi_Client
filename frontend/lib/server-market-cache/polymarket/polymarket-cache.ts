import { BaseServerMarketCache } from '../base-cache'
import type { CachedMarket, SelectedToken } from '../types'

/**
 * Polymarket-specific cache service
 */
export class PolymarketServerCache extends BaseServerMarketCache {
  /**
   * Fetch markets from Polymarket CLOB API with cursor pagination
   */
  async fetchMarkets(): Promise<CachedMarket[]> {
    const allMarkets: CachedMarket[] = []
    let nextCursor: string | null = null
    const maxMarkets = 5000 // Reduced for faster iteration
    const batchSize = 500 // Polymarket API limit per request
    let offset = 0
    
    try {
      ////console.log(`🔄 Starting Polymarket pagination (target: ${maxMarkets} markets)`)
      
      while (allMarkets.length < maxMarkets) {
        // Build URL with cursor pagination
        let url = `https://gamma-api.polymarket.com/markets?active=true&closed=false&archived=false&limit=${batchSize}&offset=${offset}`
        if (offset < maxMarkets) {
          offset += batchSize
        }
        
        ////console.log(`📥 Fetching Polymarket batch ${Math.ceil(allMarkets.length / batchSize) + 1}...`)
        ////console.log(`🔗 Request URL: ${url}`)
        
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
        ////console.log('🔍 API Response structure:')
        ////console.log('- Response keys:', Object.keys(data))
        ////console.log('- next_cursor value:', data.next_cursor)
        ////console.log('- next_cursor type:', typeof data.next_cursor)
        ////console.log('- Raw response sample:', JSON.stringify(data, null, 2).substring(0, 500) + '...')
        
        const batchMarkets = this.transformApiResponse(data)
        
        if (batchMarkets.length === 0) {
          //console.log('📭 No more Polymarket markets available')
          break
        }
        
        allMarkets.push(...batchMarkets)
        ////console.log(`✅ Polymarket batch complete: ${batchMarkets.length} markets (total: ${allMarkets.length})`)
        
        // Check for next cursor
        nextCursor = data.next_cursor || null
        ////console.log('🔗 Offset', offset)

        
        // Small delay to be respectful to the API
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      
      //console.log(`🎯 Polymarket fetch complete: ${allMarkets.length} markets cached`)
      return allMarkets.slice(0, maxMarkets) // Ensure we don't exceed target
      
    } catch (error) {
      console.error('Failed to fetch from CLOB API:', error)
      return allMarkets // Return whatever we managed to fetch
    }
  }

  /**
   * Transform CLOB API response to our cached market format
   */
  transformApiResponse(apiData: any): CachedMarket[] {
    const markets: CachedMarket[] = []
    const marketsList = apiData 
    
    //console.error("Typeof marketslist", typeof(marketsList))

    if (Array.isArray(marketsList)) {
      for (const market of marketsList) {
        const tokenPair = this.extractTokenPair(market)
        
        const marketId = String(market.id || market.conditionId)
        console.log('🔍 DEBUG: Creating market with ID:', marketId, 'type:', typeof marketId)
        console.log('🔍 DEBUG: Original market.id:', market.id, 'market.conditionId:', market.conditionId)
        
        markets.push({
          id: marketId,
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
    
    //Visualize the market data i am recieving?
    console.log(market)

    if (market.clobTokenIds && Array.isArray(market.clobTokenIds)) {
      return market.clobTokenIds
    }
    else if (market.clobTokenIds) {
      return JSON.parse(market.clobTokenIds)
    } else {
      return ["None", "None"]
    }
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
   * Search Polymarket markets specifically
   */
  searchPolymarketMarkets(query: string, maxResults: number = 50): CachedMarket[] {
    const results: CachedMarket[] = []
    const lowercaseQuery = query.toLowerCase()

    // Count markets by platform for debugging
    let platformCount = 0
    for (const market of this.memoryCache.values()) {
      if (market.platform === 'polymarket') platformCount++
    }

    //console.log(`🔍 Searching for "${query}" in ${platformCount} Polymarket markets only`)

    for (const market of this.memoryCache.values()) {
      // Skip markets from other platforms
      if (market.platform !== 'polymarket') continue
      
      if (results.length >= maxResults) break

      const titleMatch = market.title?.toLowerCase().includes(lowercaseQuery) || false
      const slugMatch = market.slug?.toLowerCase().includes(lowercaseQuery) || false

      if (titleMatch || slugMatch) {
        //console.log(`✅ Found Polymarket match: "${market.title}"`)
        results.push(market)
      }
    }

    //console.log(`🎯 Polymarket search completed: ${results.length} results found`)

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
    console.log('🔍 DEBUG: storeSelectedToken called with marketId:', marketId)
    console.log('🔍 DEBUG: Memory cache size:', this.memoryCache.size)
    console.log('🔍 DEBUG: All cached market IDs:', Array.from(this.memoryCache.keys()))
    console.log('🔍 DEBUG: Market ID type:', typeof marketId)
    console.log('🔍 DEBUG: Market ID value:', JSON.stringify(marketId))
    
    const market = this.getMarket(marketId)
    console.log('🔍 DEBUG: getMarket result:', market ? 'Found' : 'Not found')
    
    if (!market) {
      console.warn('Market not found for token storage:', marketId)
      console.warn('Available market IDs:', Array.from(this.memoryCache.keys()).slice(0, 10))
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

    //console.log(`Stored token pair for market ${marketId}:`, tokenPair)
  }

  /**
   * Update cache with fresh market data
   */
  async refreshCache(): Promise<void> {
    try {
      const markets = await this.fetchMarkets()
      
      // Update memory cache
      this.memoryCache.clear()
      console.log('🔍 DEBUG: Refreshing cache with', markets.length, 'markets')
      
      for (const market of markets) {
        console.log('🔍 DEBUG: Storing market in cache - ID:', market.id, 'type:', typeof market.id)
        this.memoryCache.set(market.id, market)
      }

      console.log('🔍 DEBUG: Cache populated with', this.memoryCache.size, 'markets')
      console.log('🔍 DEBUG: First 5 cache keys:', Array.from(this.memoryCache.keys()).slice(0, 5))

      this.lastUpdate = Date.now()
      //console.log(`Polymarket cache updated with ${markets.length} markets`)
    } catch (error) {
      console.error('Failed to refresh Polymarket cache:', error)
    }
  }
}