import { NextResponse } from 'next/server'
import { serverMarketCache } from '@/lib/server-market-cache'

export async function GET() {
  try {
    // Check if cache needs initial population (first load only)
    const stats = serverMarketCache.getCacheStats()
    
    if (stats.marketCount === 0) {
      console.log('🚀 First load: refreshing empty cache...')
      await serverMarketCache.refreshCache()
    } else {
      console.log('📋 Using existing cached data - no automatic refresh')
    }
    
    const updatedStats = serverMarketCache.getCacheStats()
    
    // Get all markets from server cache
    const markets = Array.from((serverMarketCache as any).memoryCache.values())
    
    return NextResponse.json({
      success: true,
      markets,
      stats: updatedStats
    })
  } catch (error) {
    console.error('Markets API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch markets' },
      { status: 500 }
    )
  }
}
