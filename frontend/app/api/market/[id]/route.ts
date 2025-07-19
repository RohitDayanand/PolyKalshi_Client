import { NextRequest, NextResponse } from 'next/server'
import { marketSearchService } from '@/lib/search-service'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params

    if (!id) {
      return NextResponse.json(
        { error: 'Market ID is required' },
        { status: 400 }
      )
    }

    console.log('🔍 API: Getting market for ID:', id)
    
    // Check cache stats
    const cacheStats = await marketSearchService.getCacheStats()
    console.log('🔍 API: Cache stats:', cacheStats)
    
    if (cacheStats.marketCount === 0) {
      console.log('🔍 API: Cache is empty, returning not found')
      return NextResponse.json(
        { 
          error: 'Cache is empty - please search first to populate cache',
          cacheStats 
        },
        { status: 404 }
      )
    }

    // Get market using the same service pattern as search API
    const market = await marketSearchService.getMarket(id)
    
    if (!market) {
      console.log('🔍 API: Market not found in cache')
      return NextResponse.json(
        { 
          error: 'Market not found in cache',
          searchedId: id,
          cacheStats
        },
        { status: 404 }
      )
    }

    console.log('🔍 API: Market found:', market.title)
    console.log('🔍 API: Market clobTokenIds:', market.clobTokenIds)
    console.log('🔍 API: Market outcomes:', market.outcomes)

    return NextResponse.json({
      success: true,
      data: market,
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    console.error('Market API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch market' },
      { status: 500 }
    )
  }
}