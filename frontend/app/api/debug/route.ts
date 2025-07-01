import { NextRequest, NextResponse } from 'next/server'
import { serverMarketCache } from '@/lib/server-market-cache'
import type { CachedMarket } from '@/lib/server-market-cache'

/**
 * Unified Debug API Endpoint
 * Consolidates all debug functionality into a single route with query parameters
 * 
 * Usage:
 * - /api/debug?type=cache - Cache statistics and platform distribution
 * - /api/debug?type=kalshi - Kalshi-specific debugging
 * - /api/debug?type=clob - Polymarket CLOB API debugging  
 * - /api/debug?type=search&query=NBA - Search functionality debugging
 * - /api/debug?type=markets - Market sample debugging
 * - /api/debug (no params) - Full system debug report
 */

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const debugType = searchParams.get('type')
  const query = searchParams.get('query')

  try {
    switch (debugType) {
      case 'cache':
        return handleCacheDebug()
      case 'kalshi':
        return handleKalshiDebug()
      case 'clob':
        return handleClobDebug()
      case 'search':
        return handleSearchDebug(query || 'NBA')
      case 'markets':
        return handleMarketsDebug()
      default:
        return handleFullSystemDebug()
    }
  } catch (error) {
    console.error('Debug API error:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      },
      { status: 500 }
    )
  }
}

/**
 * Cache statistics and platform distribution
 */
async function handleCacheDebug() {
  const cache = serverMarketCache
  const cacheStats = cache.getCacheStats()
  
  // Get all cached markets for platform analysis
  const allMarkets = cache.searchMarkets('', 1000)
  
  const platformCounts = {
    polymarket: allMarkets.filter((m: CachedMarket) => m.platform === 'polymarket').length,
    kalshi: allMarkets.filter((m: CachedMarket) => m.platform === 'kalshi').length,
    undefined: allMarkets.filter((m: CachedMarket) => !m.platform).length,
    other: allMarkets.filter((m: CachedMarket) => 
      m.platform && m.platform !== 'polymarket' && m.platform !== 'kalshi'
    ).length
  }

  return NextResponse.json({
    success: true,
    type: 'cache',
    cacheStats,
    platformCounts,
    timestamp: new Date().toISOString()
  })
}

/**
 * Kalshi-specific debugging
 */
async function handleKalshiDebug() {
  const cache = serverMarketCache
  const cacheStats = cache.getCacheStats()
  
  // Get all cached markets
  const allMarkets = cache.searchMarkets('', 1000)
  
  // Platform distribution
  const platformCounts = {
    polymarket: allMarkets.filter((m: CachedMarket) => m.platform === 'polymarket').length,
    kalshi: allMarkets.filter((m: CachedMarket) => m.platform === 'kalshi').length,
    undefined: allMarkets.filter((m: CachedMarket) => !m.platform).length,
    other: allMarkets.filter((m: CachedMarket) => 
      m.platform && m.platform !== 'polymarket' && m.platform !== 'kalshi'
    ).length
  }
  
  // Get samples from each platform  
  const polymarketSamples = allMarkets
    .filter((m: CachedMarket) => m.platform === 'polymarket')
    .slice(0, 2)
    .map(market => ({
      id: market.id,
      title: market.title,
      platform: market.platform,
      category: market.category
    }))
  
  const kalshiSamples = allMarkets
    .filter((m: CachedMarket) => m.platform === 'kalshi')
    .slice(0, 2)
    .map(market => ({
      id: market.id,
      title: market.title,
      platform: market.platform,
      category: market.category
    }))

  // Test direct Kalshi API call
  let rawKalshiSample = null
  try {
    const response = await fetch('https://api.elections.kalshi.com/trade-api/v2/markets?limit=1&status=open')
    if (response.ok) {
      const data = await response.json()
      rawKalshiSample = data.markets?.[0] || null
    }
  } catch (error) {
    console.error('Raw Kalshi API test failed:', error)
  }

  return NextResponse.json({
    success: true,
    type: 'kalshi',
    cacheStats,
    platformCounts,
    samples: {
      polymarket: polymarketSamples,
      kalshi: kalshiSamples
    },
    rawKalshiSample,
    totalMarkets: allMarkets.length,
    timestamp: new Date().toISOString()
  })
}

/**
 * Polymarket CLOB API debugging
 */
async function handleClobDebug() {
  try {
    console.log('🔍 Fetching from CLOB API...')
    const response = await fetch('https://clob.polymarket.com/markets?active=true&limit=5', {
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      throw new Error(`CLOB API request failed: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    
    // Analyze response structure
    const analysis = {
      responseKeys: Object.keys(data),
      dataType: typeof data,
      hasDataProperty: !!data.data,
      dataIsArray: Array.isArray(data.data),
      dataLength: data.data?.length || 0
    }

    let firstMarketAnalysis = null
    if (Array.isArray(data.data) && data.data.length > 0) {
      const firstMarket = data.data[0]
      firstMarketAnalysis = {
        marketKeys: Object.keys(firstMarket),
        hasConditionId: !!firstMarket.condition_id,
        hasQuestion: !!firstMarket.question,
        hasTokens: !!firstMarket.tokens,
        tokensIsArray: Array.isArray(firstMarket.tokens),
        tokensLength: firstMarket.tokens?.length || 0,
        sampleMarket: {
          condition_id: firstMarket.condition_id,
          question: firstMarket.question?.substring(0, 100) + '...',
          category: firstMarket.category
        }
      }
    }

    return NextResponse.json({
      success: true,
      type: 'clob',
      analysis,
      firstMarketAnalysis,
      rawSample: data.data?.[0] || null,
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    return NextResponse.json({
      success: false,
      type: 'clob',
      error: error instanceof Error ? error.message : 'Unknown error',
      timestamp: new Date().toISOString()
    })
  }
}

/**
 * Search functionality debugging
 */
async function handleSearchDebug(query: string) {
  const cacheStats = serverMarketCache.getCacheStats()
  
  if (cacheStats.marketCount === 0) {
    // DISABLED automatic refresh to prevent polling
    // console.log('Cache is empty, refreshing...')
    // await serverMarketCache.refreshCache()
    console.log('Cache is empty, but automatic refresh is disabled')
  }

  // Search directly in cache
  console.log(`Searching for "${query}" in cache...`)
  const searchResults = serverMarketCache.searchMarkets(query, 5)
  
  // Get sample markets for context
  const allMarkets = []
  let count = 0
  for (const market of (serverMarketCache as any).memoryCache.values()) {
    if (count >= 5) break
    allMarkets.push({
      id: market.id,
      title: market.title,
      slug: market.slug,
      category: market.category,
      platform: market.platform
    })
    count++
  }

  return NextResponse.json({
    success: true,
    type: 'search',
    query,
    cacheStats,
    searchResults: searchResults.map(market => ({
      id: market.id,
      title: market.title,
      platform: market.platform,
      category: market.category
    })),
    sampleMarkets: allMarkets,
    timestamp: new Date().toISOString()
  })
}

/**
 * Market sample debugging
 */
async function handleMarketsDebug() {
  // DISABLED automatic refresh to prevent polling
  // await serverMarketCache.refreshCache()
  
  // Get cache stats
  const stats = serverMarketCache.getCacheStats()
  
  // Get first 10 markets to debug
  const markets = []
  let count = 0
  for (const market of (serverMarketCache as any).memoryCache.values()) {
    if (count >= 10) break
    markets.push({
      id: market.id,
      title: market.title,
      slug: market.slug,
      category: market.category,
      platform: market.platform,
      tokenCount: market.clobTokenIds?.length || 0,
      active: market.active
    })
    count++
  }

  return NextResponse.json({
    success: true,
    type: 'markets',
    stats,
    sampleMarkets: markets,
    timestamp: new Date().toISOString()
  })
}

/**
 * Full system debug report
 */
async function handleFullSystemDebug() {
  const cache = serverMarketCache
  const cacheStats = cache.getCacheStats()
  
  // Get platform distribution
  const allMarkets = cache.searchMarkets('', 1000)
  const platformCounts = {
    polymarket: allMarkets.filter((m: CachedMarket) => m.platform === 'polymarket').length,
    kalshi: allMarkets.filter((m: CachedMarket) => m.platform === 'kalshi').length,
    undefined: allMarkets.filter((m: CachedMarket) => !m.platform).length,
    other: allMarkets.filter((m: CachedMarket) => 
      m.platform && m.platform !== 'polymarket' && m.platform !== 'kalshi'
    ).length
  }

  // Test external APIs
  const apiTests = {
    kalshi: { working: false, error: null as string | null },
    clob: { working: false, error: null as string | null }
  }

  try {
    const kalshiResponse = await fetch('https://api.elections.kalshi.com/trade-api/v2/markets?limit=1&status=open')
    apiTests.kalshi.working = kalshiResponse.ok
    if (!kalshiResponse.ok) {
      apiTests.kalshi.error = `${kalshiResponse.status} ${kalshiResponse.statusText}`
    }
  } catch (error) {
    apiTests.kalshi.error = error instanceof Error ? error.message : 'Unknown error'
  }

  try {
    const clobResponse = await fetch('https://clob.polymarket.com/markets?active=true&limit=1')
    apiTests.clob.working = clobResponse.ok
    if (!clobResponse.ok) {
      apiTests.clob.error = `${clobResponse.status} ${clobResponse.statusText}`
    }
  } catch (error) {
    apiTests.clob.error = error instanceof Error ? error.message : 'Unknown error'
  }

  return NextResponse.json({
    success: true,
    type: 'full-system',
    cacheStats,
    platformCounts,
    apiTests,
    systemHealth: {
      cachePopulated: cacheStats.marketCount > 0,
      cacheStale: cacheStats.isStale,
      kalshiApiWorking: apiTests.kalshi.working,
      clobApiWorking: apiTests.clob.working
    },
    timestamp: new Date().toISOString()
  })
}
