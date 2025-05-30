import { NextRequest, NextResponse } from 'next/server'
import { marketSearchService } from '@/lib/search-service'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { marketId, tokenId, outcomeName, marketTitle } = body

    if (!marketId || !tokenId || !outcomeName || !marketTitle) {
      return NextResponse.json(
        { error: 'marketId, tokenId, outcomeName, and marketTitle are required' },
        { status: 400 }
      )
    }

    // Store the selected token (will store both tokens from the pair)
    await marketSearchService.storeSelectedToken(marketId, tokenId, outcomeName, marketTitle)

    return NextResponse.json({
      success: true,
      message: 'Token pair stored successfully',
      data: {
        marketId,
        tokenId,
        outcomeName,
        marketTitle,
        timestamp: new Date().toISOString()
      }
    })
  } catch (error) {
    console.error('Token selection API error:', error)
    return NextResponse.json(
      { error: 'Failed to store token selection' },
      { status: 500 }
    )
  }
}

export async function GET(request: NextRequest) {
  try {
    const selectedTokens = await marketSearchService.getSelectedTokens()
    
    return NextResponse.json({
      success: true,
      data: selectedTokens,
      count: selectedTokens.length,
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    console.error('Get selected tokens API error:', error)
    return NextResponse.json(
      { error: 'Failed to retrieve selected tokens' },
      { status: 500 }
    )
  }
}
