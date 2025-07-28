import { NextRequest } from 'next/server'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const platform = searchParams.get('platform')
  const query = searchParams.get('query')

  if (!platform || !query) {
    return new Response('Platform and query parameters are required', { status: 400 })
  }

  if (platform !== 'polymarket' && platform !== 'kalshi') {
    return new Response('Platform must be either "polymarket" or "kalshi"', { status: 400 })
  }

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder()

      const sendEvent = (type: string, data: any) => {
        const eventData = `data: ${JSON.stringify({ type, data })}\n\n`
        controller.enqueue(encoder.encode(eventData))
      }

      try {
        // Import here to avoid top-level imports that might cause issues
        const { marketSearchService } = await import('@/lib/search-service')
        
        sendEvent('progress', { 
          stage: 'initializing', 
          message: 'Starting search...', 
          progress: 0 
        })

        // Check cache status first
        const cacheStats = await marketSearchService.getCacheStats()
        
        if (cacheStats.marketCount === 0) {
          sendEvent('progress', { 
            stage: 'cache_loading', 
            message: 'Cache is empty, warming up...', 
            progress: 10 
          })

          // Start cache refresh with progress tracking
          await refreshCacheWithProgress(sendEvent, platform)
        } else {
          sendEvent('progress', { 
            stage: 'cache_ready', 
            message: 'Cache is ready', 
            progress: 50 
          })
        }

        sendEvent('progress', { 
          stage: 'searching', 
          message: `Searching ${platform} markets...`, 
          progress: 70 
        })

        // Perform the actual search
        const results = await performSearch(platform, query)

        sendEvent('progress', { 
          stage: 'complete', 
          message: `Found ${results.length} markets`, 
          progress: 100 
        })

        // Send final results
        sendEvent('results', {
          success: true,
          data: results,
          platform,
          query,
          timestamp: new Date().toISOString(),
          cache: cacheStats
        })

      } catch (error) {
        console.error('Search stream error:', error)
        sendEvent('error', {
          message: 'Search failed',
          error: error instanceof Error ? error.message : 'Unknown error'
        })
      } finally {
        controller.close()
      }
    }
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    }
  })
}

async function refreshCacheWithProgress(
  sendEvent: (type: string, data: any) => void, 
  platform: 'polymarket' | 'kalshi'
) {
  const { serverMarketCache } = await import('@/lib/server-market-cache')
  
  if (platform === 'polymarket') {
    sendEvent('progress', { 
      stage: 'cache_loading', 
      message: 'Fetching Polymarket markets...', 
      progress: 20 
    })
    
    // Get the polymarket cache for more granular progress
    const polymarketCache = serverMarketCache.getPolymarketCache()
    
    // Since we can't easily modify the existing fetch method, we'll simulate progress
    const refreshPromise = polymarketCache.refreshCache()
    
    // Simulate progress updates during cache refresh
    const progressInterval = setInterval(() => {
      const currentStats = serverMarketCache.getCacheStats()
      const estimatedProgress = Math.min(30 + (currentStats.marketCount / 5000) * 20, 45)
      
      sendEvent('progress', { 
        stage: 'cache_loading', 
        message: `Loading markets: ${currentStats.marketCount} cached...`, 
        progress: estimatedProgress 
      })
    }, 500)
    
    await refreshPromise
    clearInterval(progressInterval)
    
  } else {
    sendEvent('progress', { 
      stage: 'cache_loading', 
      message: 'Fetching Kalshi markets...', 
      progress: 20 
    })
    
    const kalshiCache = serverMarketCache.getKalshiCache()
    await kalshiCache.refreshCache()
  }
  
  sendEvent('progress', { 
    stage: 'cache_ready', 
    message: 'Cache loaded successfully', 
    progress: 50 
  })
}

async function performSearch(platform: 'polymarket' | 'kalshi', query: string) {
  const { marketSearchService } = await import('@/lib/search-service')
  
  if (platform === 'polymarket') {
    return await marketSearchService.searchPolymarketQuestions(query)
  } else {
    return await marketSearchService.searchKalshiQuestions(query)
  }
}