import { NextRequest, NextResponse } from 'next/server'
import { serverMarketCache } from '@/lib/server-market-cache'

export async function POST(request: NextRequest) {
  try {
    console.log('🔄 Triggering cache refresh...')
    
    // Force refresh the cache
    await serverMarketCache.refreshCache()
    
    // Get updated stats
    const stats = serverMarketCache.getCacheStats()
    
    console.log('✅ Cache refresh completed')
    
    return NextResponse.json({
      success: true,
      message: 'Cache refreshed successfully',
      stats
    })
  } catch (error) {
    console.error('❌ Error refreshing cache:', error)
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 })
  }
}
