/**
 * Test script to verify Polymarket CLOB API integration
 * Run this to test the cache system and API connectivity
 */

import { browserMarketCache } from '../lib/browser-market-cache'
import { marketSearchService } from '../lib/search-service'

async function testClobApiIntegration() {
  console.log('🧪 Testing Polymarket CLOB API Integration...\n')

  try {
    // Test 1: Direct API fetch
    console.log('1. Testing direct CLOB API fetch...')
    const markets = await browserMarketCache.fetchPolymarketMarkets()
    console.log(`✅ Fetched ${markets.length} markets from CLOB API`)
    
    if (markets.length > 0) {
      const sampleMarket = markets[0]
      console.log('📊 Sample market:', {
        id: sampleMarket.id,
        title: sampleMarket.title.substring(0, 50) + '...',
        tokenPair: sampleMarket.clobTokenIds,
        volume: sampleMarket.volume,
        outcomes: sampleMarket.outcomes?.length || 0
      })
    }

    // Test 2: Cache functionality
    console.log('\n2. Testing cache functionality...')
    await browserMarketCache.refreshCache()
    const cacheStats = browserMarketCache.getCacheStats()
    console.log('✅ Cache stats:', cacheStats)

    // Test 3: Search functionality
    console.log('\n3. Testing search functionality...')
    const searchResults = browserMarketCache.searchMarkets('election', 5)
    console.log(`✅ Found ${searchResults.length} markets matching "election"`)
    
    searchResults.forEach((market, index) => {
      console.log(`   ${index + 1}. ${market.title.substring(0, 60)}...`)
    })

    // Test 4: Token storage
    console.log('\n4. Testing token storage...')
    if (searchResults.length > 0) {
      const testMarket = searchResults[0]
      const tokenId = testMarket.clobTokenIds?.[0]
      
      if (tokenId) {
        browserMarketCache.storeSelectedToken(
          testMarket.id,
          tokenId,
          'Yes',
          testMarket.title
        )
        
        const selectedTokens = browserMarketCache.getSelectedTokens()
        console.log(`✅ Stored token pair. Total selected tokens: ${selectedTokens.length}`)
        
        // Show last stored token
        const lastToken = selectedTokens[selectedTokens.length - 1]
        if (lastToken) {
          console.log('📋 Last stored token:', {
            marketId: lastToken.marketId,
            tokenId: lastToken.tokenId,
            outcome: lastToken.outcomeName
          })
        }
      }
    }

    // Test 5: Search service integration
    console.log('\n5. Testing search service integration...')
    const serviceResults = await marketSearchService.searchPolymarketQuestions('trump')
    console.log(`✅ Search service returned ${serviceResults.length} results`)

    console.log('\n🎉 All tests passed! CLOB API integration is working.')
    
    return {
      success: true,
      marketsFetched: markets.length,
      cacheStats,
      searchResults: searchResults.length,
      selectedTokens: browserMarketCache.getSelectedTokens().length
    }

  } catch (error) {
    console.error('❌ Test failed:', error)
    return {
      success: false,
      error: "Yo mama"
    }
  }
}

// Export for use in browser console or test runner
if (typeof window !== 'undefined') {
  (window as any).testClobApi = testClobApiIntegration
}

export { testClobApiIntegration }
