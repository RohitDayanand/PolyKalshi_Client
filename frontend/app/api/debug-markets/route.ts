import { NextResponse } from 'next/server'
import { serverMarketCache } from '@/lib/server-market-cache'

export async function GET() {
  try {
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
        tokenCount: market.clobTokenIds?.length || 0
      })
      count++
    }
    
    return NextResponse.json({
      success: true,
      stats,
      sampleMarkets: markets
    })
  } catch (error) {
    console.error('Debug markets error:', error)
    return NextResponse.json(
      { error: 'Failed to debug markets' },
      { status: 500 }
    )
  }
}
