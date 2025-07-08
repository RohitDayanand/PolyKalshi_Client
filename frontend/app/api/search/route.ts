import { NextRequest, NextResponse } from 'next/server'
import { marketSearchService } from '@/lib/search-service'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const platform = searchParams.get('platform')
  const query = searchParams.get('query')

  if (!platform || !query) {
    return NextResponse.json(
      { error: 'Platform and query parameters are required' },
      { status: 400 }
    )
  }

  if (platform !== 'polymarket' && platform !== 'kalshi') {
    return NextResponse.json(
      { error: 'Platform must be either "polymarket" or "kalshi"' },
      { status: 400 }
    )
  }

  try {
    // Use the search service for custom logic with CLOB API integration
    const results = await searchMarkets(platform, query)
    
    // Include cache stats for debugging
    const cacheStats = await marketSearchService.getCacheStats()
    
    console.log('🔍 SEARCH API: Cache stats after search:', cacheStats)
    
    return NextResponse.json({
      success: true,
      data: results,
      platform,
      query,
      timestamp: new Date().toISOString(),
      cache: {
        marketCount: cacheStats.marketCount,
        lastUpdate: cacheStats.lastUpdate,
        isStale: cacheStats.isStale
      }
    })
  } catch (error) {
    console.error('Search API error:', error)
    return NextResponse.json(
      { error: 'Failed to search markets' },
      { status: 500 }
    )
  }
}

// Main search function using the service
async function searchMarkets(platform: 'polymarket' | 'kalshi', query: string) {
  if (platform === 'polymarket') {
    return await marketSearchService.searchPolymarketQuestions(query)
  } else {
    return await marketSearchService.searchKalshiQuestions(query)
  }
}
