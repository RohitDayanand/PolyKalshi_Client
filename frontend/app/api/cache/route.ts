import { NextRequest, NextResponse } from 'next/server'
import { marketSearchService } from '@/lib/search-service'

export async function GET(request: NextRequest) {
  try {
    const cacheStats = await marketSearchService.getCacheStats()
    const selectedTokens = await marketSearchService.getSelectedTokens()
    
    return NextResponse.json({
      success: true,
      cache: {
        ...cacheStats,
        selectedTokenCount: selectedTokens.length
      },
      selectedTokens: selectedTokens.slice(0, 10), // Show last 10 for debugging
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    console.error('Cache status API error:', error)
    return NextResponse.json(
      { error: 'Failed to get cache status' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { action } = body

    if (action === 'refresh') {
      // This will trigger a cache refresh on next search
      return NextResponse.json({
        success: true,
        message: 'Cache refresh will occur on next search request',
        timestamp: new Date().toISOString()
      })
    }

    if (action === 'clear') {
      // Clear the cache
      await marketSearchService.clearCache()
      return NextResponse.json({
        success: true,
        message: 'Cache cleared successfully',
        timestamp: new Date().toISOString()
      })
    }

    return NextResponse.json(
      { error: 'Invalid action. Use "refresh" or "clear" to manage cache.' },
      { status: 400 }
    )
  } catch (error) {
    console.error('Cache action API error:', error)
    return NextResponse.json(
      { error: 'Failed to execute cache action' },
      { status: 500 }
    )
  }
}
