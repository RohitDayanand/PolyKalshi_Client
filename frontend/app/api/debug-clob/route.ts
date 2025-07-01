import { NextResponse } from 'next/server'

async function debugClobApi() {
  try {
    console.log('🔍 Fetching from CLOB API...')
    const response = await fetch('https://clob.polymarket.com/markets?active=true&limit=5', {
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      throw new Error(`CLOB API request failed: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    
    console.log('📦 Raw API Response Structure:')
    console.log('- Response keys:', Object.keys(data))
    console.log('- Data type:', typeof data)
    
    if (data.data) {
      console.log('- data.data type:', typeof data.data)
      console.log('- data.data is array:', Array.isArray(data.data))
      console.log('- data.data length:', data.data?.length)
      
      if (Array.isArray(data.data) && data.data.length > 0) {
        const firstMarket = data.data[0]
        console.log('\n🎯 First Market Structure:')
        console.log('- Market keys:', Object.keys(firstMarket))
        console.log('- Sample market:', JSON.stringify(firstMarket, null, 2))
      }
    }
    
    return data
  } catch (error) {
    console.error('❌ Debug API call failed:', error)
    return null
  }
}

export async function GET() {
  try {
    const data = await debugClobApi()
    return NextResponse.json({
      success: true,
      debug: 'Check server console for detailed output',
      sampleData: data
    })
  } catch (error) {
    console.error('Debug API error:', error)
    return NextResponse.json(
      { error: 'Debug failed' },
      { status: 500 }
    )
  }
}
