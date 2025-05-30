import { NextResponse } from 'next/server'

export async function GET() {
  try {
    console.log('Fetching markets from CLOB API...')
    
    // Call the CLOB API directly to show market structure
    const response = await fetch('https://clob.polymarket.com/markets', {
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; MarketAnalyzer/1.0)'
      }
    })
    
    if (!response.ok) {
      throw new Error(`CLOB API error: ${response.status}`)
    }
    
    const data = await response.json()
    console.log('CLOB API response received')
    
    // Get first 5 markets as examples
    const examples = data.slice(0, 5).map((market: any) => ({
      id: market.condition_id,
      title: market.question,
      description: market.description,
      category: market.category,
      outcomes: market.outcomes?.map((outcome: any) => ({
        name: outcome.name,
        tokenId: outcome.token_id,
        price: outcome.price
      })),
      volume: market.volume,
      liquidity: market.liquidity,
      active: market.active,
      endDate: market.end_date_iso,
      clobTokenIds: market.clob_token_ids || [],
      rawMarket: market // Include full raw data for inspection
    }))
    
    return NextResponse.json({
      success: true,
      totalFromAPI: data.length,
      examples: examples,
      timestamp: new Date().toISOString(),
      apiUrl: 'https://clob.polymarket.com/markets'
    })
  } catch (error) {
    console.error('Direct CLOB API call failed:', error)
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Failed to fetch from CLOB API',
      success: false
    }, { status: 500 })
  }
}
