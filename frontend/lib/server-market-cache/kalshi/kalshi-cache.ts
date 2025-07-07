import { BaseServerMarketCache } from '../base-cache'
import type { CachedMarket } from '../types'

/**
 * Kalshi-specific cache service
 */
export class KalshiServerCache extends BaseServerMarketCache {
  /**
   * Fetch markets from Kalshi API with cursor pagination
   */
  async fetchMarkets(): Promise<CachedMarket[]> {
    const allMarkets: CachedMarket[] = []
    let cursor: string | null = null
    const maxMarkets = 5000 // Increased from 2500 to get more markets
    const batchSize = 200 // Reduced from 500 to be more conservative and get faster responses
    
    try {
      //console.log(`🔄 Starting Kalshi pagination (target: ${maxMarkets} markets)`)
      
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
        
        //console.log(`📥 Fetching Kalshi batch ${Math.ceil(allMarkets.length / batchSize) + 1}...`)
        //console.log(`🔗 Request URL: ${url}`)
        
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
        
        
        const batchMarkets = this.transformApiResponse(data)
        
        if (batchMarkets.length === 0) {
          //console.log('📭 No more Kalshi markets available')
          break
        }
        
        allMarkets.push(...batchMarkets)
        //console.log(`✅ Kalshi batch complete: ${batchMarkets.length} markets (total: ${allMarkets.length})`)
        
        // Check for next cursor
        cursor = data.cursor || null
        //console.log('🔗 Next cursor extracted:', cursor)
        
     
        if (!cursor) {
          //console.log('🏁 Reached end of Kalshi pagination')
          break
        }
        
        // Small delay to be respectful to the API
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      
      //console.log(`🎯 Kalshi fetch complete: ${allMarkets.length} markets cached`)
      return allMarkets.slice(0, maxMarkets) // Ensure we don't exceed target
      
    } catch (error) {
      console.error('Failed to fetch from Kalshi API:', error)
      return allMarkets // Return whatever we managed to fetch
    }
  }

  /**
   * Transform Kalshi API response to our cached market format
   */
  transformApiResponse(apiData: any): CachedMarket[] {
    //console.log('🔍 DEBUG: Sample Kalshi market data:', apiData.markets?.[0])
    //console.log('🔍 DEBUG: Available fields:', apiData.markets?.[0] ? Object.keys(apiData.markets[0]) : 'No markets')
    
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
          //console.log(`🔍 DEBUG: Market "${market.title || market.ticker}"`)
          //console.log(`  - market.volume: ${market.volume}`)
          //console.log(`  - market.dollar_volume: ${market.dollar_volume}`)
          //console.log(`  - Final volume: ${this.parseNumber(market.volume) || this.parseNumber(market.dollar_volume) || 0}`)
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
   * Search Kalshi markets specifically
   */
  searchKalshiMarkets(query: string, maxResults: number = 50): CachedMarket[] {
    const results: CachedMarket[] = []
    const lowercaseQuery = query.toLowerCase()

    // Count markets by platform for debugging
    let platformCount = 0
    for (const market of this.memoryCache.values()) {
      if (market.platform === 'kalshi') platformCount++
    }

    //console.log(`🔍 Searching for "${query}" in ${platformCount} Kalshi markets only`)

    for (const market of this.memoryCache.values()) {
      // Skip markets from other platforms
      if (market.platform !== 'kalshi') continue
      
      if (results.length >= maxResults) break

      const titleMatch = market.title?.toLowerCase().includes(lowercaseQuery) || false
      const slugMatch = market.slug?.toLowerCase().includes(lowercaseQuery) || false

      if (titleMatch || slugMatch) {
        //console.log(`✅ Found Kalshi match: "${market.title}"`)
        results.push(market)
      }
    }

    //console.log(`🎯 Kalshi search completed: ${results.length} results found`)

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
   * Update cache with fresh market data
   */
  async refreshCache(): Promise<void> {
    try {
      const markets = await this.fetchMarkets()
      
      // Update memory cache
      this.memoryCache.clear()
      for (const market of markets) {
        this.memoryCache.set(market.id, market)
      }

      this.lastUpdate = Date.now()
      //console.log(`Kalshi cache updated with ${markets.length} markets`)
    } catch (error) {
      console.error('Failed to refresh Kalshi cache:', error)
    }
  }
}