import { NextRequest, NextResponse } from 'next/server'

/*
* Borrowed from the backend websocket_server.py pydantic model implementation
*/
1
interface ArbitrageSettingsRequest {
  min_spread_threshold?: number
  min_trade_size?: number
  source?: string
}

interface ArbitrageSettingsResponse {
  success: boolean
  message: string
  old_settings?: Record<string, any> | null
  new_settings?: Record<string, any> | null
  changed_fields?: string[] | null
  errors?: string[] | null
}

export async function POST(request: NextRequest) {
  try {
    const body: ArbitrageSettingsRequest = await request.json()
    
    const backendResponse = await fetch('http://localhost:8000/api/arbitrage/settings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    const data: ArbitrageSettingsResponse = await backendResponse.json()

    if (!backendResponse.ok) {
      return NextResponse.json(data, { status: backendResponse.status })
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error('Arbitrage settings API error:', error)
    return NextResponse.json(
      { 
        success: false,
        message: 'Failed to update arbitrage settings',
        errors: ['Internal server error']
      },
      { status: 500 }
    )
  }
}