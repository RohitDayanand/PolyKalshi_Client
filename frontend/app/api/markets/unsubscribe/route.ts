import { NextResponse } from 'next/server'

interface UnsubscribeRequest {
  market_id: string
  platform: "polymarket" | "kalshi"
  client_id?: string
}

export async function POST(request: Request) {
  try {
    const body: UnsubscribeRequest = await request.json()
    
    console.log('🔥 Unsubscribe API called:', {
      market_id: body.market_id,
      platform: body.platform,
      client_id: body.client_id
    })

    // Forward the unsubscribe request to the backend
    const backendResponse = await fetch('http://localhost:8000/api/markets/unsubscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        market_id: body.market_id,
        platform: body.platform,
        client_id: body.client_id || `frontend_${Date.now()}`
      })
    })

    console.log('📡 Backend unsubscribe response status:', {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      ok: backendResponse.ok
    })

    if (!backendResponse.ok) {
      const errorText = await backendResponse.text()
      console.error('❌ Backend unsubscribe error:', errorText)
      return NextResponse.json(
        { 
          success: false, 
          error: `Backend error: ${backendResponse.status} - ${errorText}` 
        },
        { status: backendResponse.status }
      )
    }

    const backendData = await backendResponse.json()
    
    console.log('✅ Backend unsubscribe successful:', backendData)

    return NextResponse.json({
      success: true,
      market_id: body.market_id,
      platform: body.platform,
      message: 'Successfully unsubscribed from market',
      backend_response: backendData
    })

  } catch (error) {
    console.error('❌ Unsubscribe API error:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error occurred' 
      },
      { status: 500 }
    )
  }
}