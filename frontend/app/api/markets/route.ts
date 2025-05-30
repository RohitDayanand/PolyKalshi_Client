import { NextResponse } from 'next/server'
import { serverMarketCache } from '@/lib/server-market-cache'

export async function GET() {
  try {
    // Use the server cache which can make external API calls
    await serverMarketCache.refreshCache()
    const stats = serverMarketCache.getCacheStats()
    
    // Get all markets from server cache
    const markets = Array.from((serverMarketCache as any).memoryCache.values())
    
    return NextResponse.json({
      success: true,
      markets,
      stats
    })
  } catch (error) {
    console.error('Markets API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch markets' },
      { status: 500 }
    )
  }
}
