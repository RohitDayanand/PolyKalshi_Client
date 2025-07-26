import { NextRequest, NextResponse } from 'next/server'
import { serverMarketCache } from '@/lib/server-market-cache'

interface FindMarketRequest {
  platform: 'kalshi' | 'polymarket'
  identifier: string // ticker for Kalshi, condition_id for Polymarket
}

export async function POST(request: NextRequest) {
  try {
    const body: FindMarketRequest = await request.json()
    
    if (!body.platform || !body.identifier) {
      return NextResponse.json(
        { error: 'Platform and identifier are required' },
        { status: 400 }
      )
    }

    if (body.platform !== 'kalshi' && body.platform !== 'polymarket') {
      return NextResponse.json(
        { error: 'Platform must be either "kalshi" or "polymarket"' },
        { status: 400 }
      )
    }

    console.log(`🔍 Finding ${body.platform} market:`, body.identifier)

    // Check if market already exists in cache first
    const existingMarket = serverMarketCache.getMarket(body.identifier)
    if (existingMarket && existingMarket.platform === body.platform) {
      console.log('✅ Market found in cache:', existingMarket.title)
      
      // Transform to Market interface format
      const transformedMarket = {
        id: existingMarket.id,
        title: existingMarket.title,
        category: existingMarket.category,
        volume: existingMarket.volume,
        liquidity: existingMarket.liquidity,
        price: existingMarket.outcomes?.[0]?.price,
        platform: existingMarket.platform,
        lastUpdated: existingMarket.lastUpdated,
        yes_subtitle: existingMarket.yes_subtitle,
        tokenIds: existingMarket.platform === 'polymarket' ? existingMarket.clobTokenIds : undefined,
        kalshiTicker: existingMarket.platform === 'kalshi' ? existingMarket.id : undefined
      }

      return NextResponse.json({
        success: true,
        data: transformedMarket,
        source: 'cache',
        timestamp: new Date().toISOString()
      })
    }

    // Market not in cache, fetch from API
    let apiResponse: any
    let transformedMarket: any

    if (body.platform === 'kalshi') {
      // Fetch from Kalshi API by ticker
      console.log(`📡 Fetching Kalshi market: ${body.identifier}`)
      const kalshiResponse = await fetch(`https://api.elections.kalshi.com/trade-api/v2/markets/${body.identifier}`, {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      })

      if (!kalshiResponse.ok) {
        if (kalshiResponse.status === 404) {
          return NextResponse.json(
            { 
              success: false, 
              error: `Kalshi market with ticker "${body.identifier}" not found` 
            },
            { status: 404 }
          )
        }
        throw new Error(`Kalshi API error: ${kalshiResponse.status} ${kalshiResponse.statusText}`)
      }

      const kalshiData = await kalshiResponse.json()
      console.log('📥 Kalshi API response:', kalshiData.market ? 'Market found' : 'No market in response')

      if (!kalshiData.market) {
        return NextResponse.json(
          { 
            success: false, 
            error: `Kalshi market with ticker "${body.identifier}" not found` 
          },
          { status: 404 }
        )
      }

      // Transform using existing cache transformation logic
      const kalshiCache = serverMarketCache.getKalshiCache()
      const cachedMarkets = kalshiCache.transformApiResponse({ markets: [kalshiData.market] })
      
      if (cachedMarkets.length === 0) {
        return NextResponse.json(
          { 
            success: false, 
            error: `Failed to transform Kalshi market "${body.identifier}"` 
          },
          { status: 500 }
        )
      }

      const cachedMarket = cachedMarkets[0]
      
      // Add to cache
      await kalshiCache.addMarket(cachedMarket)
      
      transformedMarket = {
        id: cachedMarket.id,
        title: cachedMarket.title,
        category: cachedMarket.category,
        volume: cachedMarket.volume,
        liquidity: cachedMarket.liquidity,
        price: cachedMarket.outcomes?.[0]?.price,
        platform: cachedMarket.platform,
        lastUpdated: cachedMarket.lastUpdated,
        yes_subtitle: cachedMarket.yes_subtitle,
        kalshiTicker: cachedMarket.id
      }

    } else {
      // Fetch from Polymarket API by condition_id
      console.log(`📡 Fetching Polymarket market: ${body.identifier}`)
      
      // Try to find market by condition_id in the markets endpoint
      const polymarketResponse = await fetch(`https://gamma-api.polymarket.com/markets?condition_ids=${body.identifier}&limit=1`, {
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'Mozilla/5.0 (compatible; MarketAnalyzer/1.0)'
        }
      })

      if (!polymarketResponse.ok) {
        throw new Error(`Polymarket API error: ${polymarketResponse.status} ${polymarketResponse.statusText}`)
      }

      const polymarketData = await polymarketResponse.json()
      console.log('📥 Polymarket API response:', Array.isArray(polymarketData) ? `${polymarketData.length} markets` : 'Invalid response')

      if (!Array.isArray(polymarketData) || polymarketData.length === 0) {
        return NextResponse.json(
          { 
            success: false, 
            error: `Polymarket market with ID "${body.identifier}" not found` 
          },
          { status: 404 }
        )
      }

      // Transform using existing cache transformation logic
      const polymarketCache = serverMarketCache.getPolymarketCache()
      const cachedMarkets = polymarketCache.transformApiResponse(polymarketData)
      
      if (cachedMarkets.length === 0) {
        return NextResponse.json(
          { 
            success: false, 
            error: `Failed to transform Polymarket market "${body.identifier}"` 
          },
          { status: 500 }
        )
      }

      const cachedMarket = cachedMarkets[0]
      
      // Add to cache
      await polymarketCache.addMarket(cachedMarket)
      
      transformedMarket = {
        id: cachedMarket.id,
        title: cachedMarket.title,
        category: cachedMarket.category,
        volume: cachedMarket.volume,
        liquidity: cachedMarket.liquidity,
        price: cachedMarket.outcomes?.[0]?.price,
        platform: cachedMarket.platform,
        lastUpdated: cachedMarket.lastUpdated,
        tokenIds: cachedMarket.clobTokenIds
      }
    }

    console.log('✅ Market found and added to cache:', transformedMarket.title)

    return NextResponse.json({
      success: true,
      data: transformedMarket,
      source: 'api',
      timestamp: new Date().toISOString()
    })

  } catch (error) {
    console.error('Find market API error:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error occurred' 
      },
      { status: 500 }
    )
  }
}