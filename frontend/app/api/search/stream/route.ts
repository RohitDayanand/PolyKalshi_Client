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

        // Check global cache status (both platforms)
        const { serverMarketCache } = await import('@/lib/server-market-cache')
        const globalCacheStats = serverMarketCache.getCacheStats()
        
        if (globalCacheStats.marketCount === 0) {
          sendEvent('progress', { 
            stage: 'cache_loading', 
            message: 'Cache is empty, loading markets from all platforms...', 
            progress: 10 
          })

          // Start global cache refresh with progress tracking
          await refreshGlobalCacheWithProgress(sendEvent)
        } else {
          sendEvent('progress', { 
            stage: 'cache_ready', 
            message: `Cache is ready (${globalCacheStats.marketCount.toLocaleString()} markets from all platforms)`, 
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
          cache: globalCacheStats
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
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET',
      'Access-Control-Allow-Headers': 'Cache-Control'
    }
  })
}

async function refreshGlobalCacheWithProgress(
  sendEvent: (type: string, data: any) => void
) {
  const { serverMarketCache } = await import('@/lib/server-market-cache')
  
  sendEvent('progress', { 
    stage: 'cache_loading', 
    message: 'Fetching markets from all platforms...', 
    progress: 20 
  })
  
  // Create progress monitoring
  let currentStep = 0
  const progressInterval = setInterval(() => {
    currentStep++
    const stepProgress = Math.min(20 + (currentStep * 2), 95) // 2% per step, cap at 95%
    
    sendEvent('progress', { 
      stage: 'cache_loading', 
      message: 'Loading markets from all platforms... This usually takes 1-2 minutes. This will be much faster next time', 
      progress: Math.round(stepProgress) // Round to nearest percent
    })
  }, 1500) // Update every 1.5 seconds to match slower loading
  
  try {
    // Refresh the global cache (both platforms)
    await serverMarketCache.refreshCache()
  } finally {
    clearInterval(progressInterval)
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