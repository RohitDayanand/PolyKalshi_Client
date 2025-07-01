import { NextResponse } from 'next/server'
import { marketSearchService } from '@/lib/search-service'

export async function GET() {
  try {
    // Get cache statistics
    const cacheStats = await marketSearchService.getCacheStats()
    
    // Search for a few different topics to get variety
    const trumpResults = await marketSearchService.searchPolymarketQuestions('trump')
    const electionResults = await marketSearchService.searchPolymarketQuestions('election')  
    const bitcoinResults = await marketSearchService.searchPolymarketQuestions('bitcoin')
    
    // Get first few results from each search
    const examples = [
      ...trumpResults.slice(0, 3),
      ...electionResults.slice(0, 3), 
      ...bitcoinResults.slice(0, 3)
    ]
    
    return NextResponse.json({
      success: true,
      cacheStats,
      totalMarkets: cacheStats.marketCount,
      exampleCount: examples.length,
      examples: examples,
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    console.error('Examples API error:', error)
    return NextResponse.json(
      { error: 'Failed to get market examples' },
      { status: 500 }
    )
  }
}
