import { NextRequest, NextResponse } from 'next/server'
import { marketSearchService, type SearchConfig } from '@/lib/search-service'

export async function GET() {
  try {
    const config = marketSearchService.getConfig()
    return NextResponse.json({
      success: true,
      data: config
    })
  } catch (error) {
    console.error('Config GET error:', error)
    return NextResponse.json(
      { error: 'Failed to get search configuration' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const updates: Partial<SearchConfig> = body

    // Validate the updates
    if (updates.maxResults !== undefined && (updates.maxResults < 1 || updates.maxResults > 100)) {
      return NextResponse.json(
        { error: 'maxResults must be between 1 and 100' },
        { status: 400 }
      )
    }

    if (updates.minVolumeThreshold !== undefined && updates.minVolumeThreshold < 0) {
      return NextResponse.json(
        { error: 'minVolumeThreshold must be non-negative' },
        { status: 400 }
      )
    }

    // Update the configuration
    marketSearchService.updateConfig(updates)
    const newConfig = marketSearchService.getConfig()

    return NextResponse.json({
      success: true,
      message: 'Configuration updated successfully',
      data: newConfig
    })
  } catch (error) {
    console.error('Config POST error:', error)
    return NextResponse.json(
      { error: 'Failed to update search configuration' },
      { status: 500 }
    )
  }
}
