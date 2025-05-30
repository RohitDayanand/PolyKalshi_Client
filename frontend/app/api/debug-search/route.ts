import { NextRequest, NextResponse } from 'next/server'
import { serverMarketCache } from '@/lib/server-market-cache'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const query = searchParams.get('query') || 'NBA'

  try {
    // Check cache directly
    const cacheStats = serverMarketCache.getCacheStats()
    console.log('Cache stats:', cacheStats)
    
    if (cacheStats.marketCount === 0) {
      console.log('Cache is empty, refreshing...')
      await serverMarketCache.refreshCache()
    }

    // Search directly in cache
    console.log(`Searching for "${query}" in cache...`)
    const results = serverMarketCache.searchMarkets(query, 5)
    
    // Get first few markets for debugging
    const allMarkets = []
    let count = 0
    for (const market of (serverMarketCache as any).memoryCache.values()) {
      if (count >= 5) break
      allMarkets.push({
        id: market.id,
        title: market.title,
        slug: market.slug,
        category: market.category,
        allProps: Object.keys(market)
      })
      count++
    }

    return NextResponse.json({
      success: true,
      query,
      searchResults: results.map(r => ({ id: r.id, title: r.title })),
      cacheStats: serverMarketCache.getCacheStats(),
      sampleMarkets: allMarkets
    })
  } catch (error) {
    console.error('Debug search error:', error)
    return NextResponse.json({
      error: 'Debug search failed',
      details: (error as Error).message
    }, { status: 500 })
  }
}
