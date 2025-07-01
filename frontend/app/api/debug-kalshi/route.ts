import { NextResponse } from 'next/server'
import { serverMarketCache } from '@/lib/server-market-cache'
import type { CachedMarket } from '@/lib/server-market-cache'

export async function GET() {
  try {
    console.log('🔍 Starting debug analysis...')
    
    // Get cache instance and stats
    const cache = serverMarketCache
    const cacheStats = cache.getCacheStats()
    console.log('📊 Cache stats:', cacheStats)
    
    // Get all cached markets
    const allMarkets = cache.searchMarkets('', 1000) // Get all markets
    
    // Count by platform
    const platformCounts = {
      polymarket: allMarkets.filter((m: CachedMarket) => m.platform === 'polymarket').length,
      kalshi: allMarkets.filter((m: CachedMarket) => m.platform === 'kalshi').length,
      undefined: allMarkets.filter((m: CachedMarket) => !m.platform).length,
      other: allMarkets.filter((m: CachedMarket) => m.platform && m.platform !== 'polymarket' && m.platform !== 'kalshi').length
    }
    
    console.log('🏷️ Platform distribution:', platformCounts)
    
    // Get samples from each platform  
    const polymarketSamples = allMarkets.filter((m: CachedMarket) => m.platform === 'polymarket').slice(0, 2)
    const kalshiSamples = allMarkets.filter((m: CachedMarket) => m.platform === 'kalshi').slice(0, 2)
    
    // Also test direct Kalshi API call
    const kalshiResponse = await fetch('https://api.elections.kalshi.com/trade-api/v2/markets?limit=5&status=open', {
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      }
    })
    
    const kalshiData = kalshiResponse.ok ? await kalshiResponse.json() : { error: 'Failed to fetch from Kalshi API' }
    
    return NextResponse.json({
      success: true,
      cacheStats,
      platformCounts,
      samples: {
        polymarket: polymarketSamples.map((m: CachedMarket) => ({ 
          id: m.id, 
          title: m.title, 
          platform: m.platform, 
          category: m.category 
        })),
        kalshi: kalshiSamples.map((m: CachedMarket) => ({ 
          id: m.id, 
          title: m.title, 
          platform: m.platform, 
          category: m.category 
        }))
      },
      rawKalshiSample: kalshiData.markets?.[0] || null,
      totalMarkets: allMarkets.length,
      timestamp: new Date().toISOString()
    })
    
  } catch (error) {
    console.error('❌ Debug endpoint error:', error)
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined
    }, { status: 500 })
  }
}
