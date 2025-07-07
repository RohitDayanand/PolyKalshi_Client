import { createSlice, PayloadAction, createAsyncThunk } from '@reduxjs/toolkit'

// Backend API types (lightweight - no data storage)
interface MarketSubscriptionRequest {
  platform: "polymarket" | "kalshi"
  market_identifier: string
  client_id?: string
}

interface MarketSubscriptionResponse {
  success: boolean
  status: "pending" | "connecting" | "connected" | "failed"
  market_id: string
  platform: string
  message: string
  websocket_url: string
}

interface Market {
  id: string
  title: string
  platform?: "polymarket" | "kalshi"
  tokenIds?: string[]
  kalshiTicker?: string
}

// Only track subscription states, NOT market data
interface SubscriptionState {
  backend_market_id: string
  platform: string
  status: string
  subscribed_at: number
  // Add essential display data
  market_title: string
  original_market_id: string
}

interface ApiSubscriptionState {
  // Track which markets we've subscribed to via API
  subscriptions: Record<string, SubscriptionState>
  
  // API call state
  isLoading: boolean
  lastError: string | null
  
  // WebSocket subscription tracking
  pendingWebSocketSubscriptions: string[] // market_ids waiting for WS subscription
}

const initialState: ApiSubscriptionState = {
  subscriptions: {},
  isLoading: false,
  lastError: null,
  pendingWebSocketSubscriptions: [],
}

// Async thunk for backend API call
export const callSubscriptionAPI = createAsyncThunk(
  'apiSubscription/callSubscriptionAPI',
  async ({ platform, market }: { platform: "polymarket" | "kalshi"; market: Market }) => {
    // For Polymarket: pass full tokenIds array as JSON string for proper pair handling
    // For Kalshi: pass single ticker identifier
    const marketIdentifier = platform === "polymarket" 
      ? JSON.stringify(market.tokenIds)  // Full token array as JSON
      : (market.kalshiTicker || market.id)              // Single ticker for Kalshi
    
    console.log('🔍 Market Identifier Extraction:', { 
      platform, 
      marketTitle: market.title,
      originalTokenIds: market.tokenIds,
      originalKalshiTicker: market.kalshiTicker,
      extractedIdentifier: marketIdentifier 
    })

    const request: MarketSubscriptionRequest = {
      platform,
      market_identifier: marketIdentifier,
      client_id: `frontend_${Date.now()}`
    }

    console.log('📤 Calling Backend API:', {
      url: 'http://localhost:8000/api/markets/subscribe',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: request,
      requestString: JSON.stringify(request)
    })

    const response = await fetch('http://localhost:8000/api/markets/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    })

    console.log('📡 HTTP Response Status:', {
      status: response.status,
      statusText: response.statusText,
      ok: response.ok,
      headers: Object.fromEntries(response.headers.entries())
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('❌ HTTP Error Response:', errorText)
      throw new Error(`HTTP ${response.status}: ${response.statusText} - ${errorText}`)
    }

    const apiResponse: MarketSubscriptionResponse = await response.json()
    console.log('📥 Backend API Response:', {
      success: apiResponse.success,
      status: apiResponse.status,
      market_id: apiResponse.market_id,
      platform: apiResponse.platform,
      message: apiResponse.message,
      websocket_url: apiResponse.websocket_url,
      market_info: apiResponse.market_id,
      fullResponse: apiResponse
    })

    if (!apiResponse.success) {
      throw new Error(`Backend error: ${apiResponse.message}`)
    }

    return { apiResponse, market, platform }
  }
)

export const apiSubscriptionSlice = createSlice({
  name: 'apiSubscription',
  initialState,
  reducers: {
    // Mark WebSocket subscription as completed
    markWebSocketSubscribed: (state, action: PayloadAction<string>) => {
      const backend_market_id = action.payload
      console.log('🏪 Redux Reducer - apiSubscription/markWebSocketSubscribed:', backend_market_id)
      
      // Remove from pending list
      state.pendingWebSocketSubscriptions = state.pendingWebSocketSubscriptions.filter(
        id => id !== backend_market_id
      )
      
      // Update subscription status
      const subscription = Object.values(state.subscriptions).find(
        sub => sub.backend_market_id === backend_market_id
      )
      //Isn't this mutating state in place???
      if (subscription) {
        subscription.status = 'websocket_connected'
      }
    },

    // Update subscription status (from WebSocket messages)
    updateSubscriptionStatus: (state, action: PayloadAction<{
      backend_market_id: string
      status: string
    }>) => {
      const { backend_market_id, status } = action.payload
      console.log('🏪 Redux Reducer - apiSubscription/updateSubscriptionStatus:', { backend_market_id, status })
      
      const subscription = Object.values(state.subscriptions).find(
        sub => sub.backend_market_id === backend_market_id
      )
      if (subscription) {
        subscription.status = status
      }
    },

    // Remove subscription
    removeSubscription: (state, action: PayloadAction<string>) => {
      const marketId = action.payload
      console.log('🏪 Redux Reducer - apiSubscription/removeSubscription:', marketId)
      delete state.subscriptions[marketId]
    },

    clearError: (state) => {
      state.lastError = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(callSubscriptionAPI.pending, (state) => {
        state.isLoading = true
        state.lastError = null
      })
      .addCase(callSubscriptionAPI.fulfilled, (state, action) => {
        const { apiResponse, market, platform } = action.payload
        console.log('✅ API subscription successful:', apiResponse.market_id)
        
        state.isLoading = false
        
        // Track the subscription (NOT the data)
        state.subscriptions[market.id] = {
          backend_market_id: apiResponse.market_id,
          platform,
          status: apiResponse.status,
          subscribed_at: Date.now(),
          market_title: market.title,
          original_market_id: market.id
        }
        
        // Add to pending WebSocket subscriptions
        state.pendingWebSocketSubscriptions.push(apiResponse.market_id)
      })
      .addCase(callSubscriptionAPI.rejected, (state, action) => {
        console.error('❌ API subscription failed:', action.error.message)
        state.isLoading = false
        state.lastError = action.error.message || 'API call failed'
      })
  }
})

export const {
  markWebSocketSubscribed,
  updateSubscriptionStatus,
  removeSubscription,
  clearError,
} = apiSubscriptionSlice.actions

export default apiSubscriptionSlice.reducer

// Selectors
export const selectIsLoading = (state: any) => state.apiSubscription.isLoading
export const selectLastError = (state: any) => state.apiSubscription.lastError
export const selectSubscriptions = (state: any) => state.apiSubscription.subscriptions
export const selectPendingWebSocketSubscriptions = (state: any) => state.apiSubscription.pendingWebSocketSubscriptions
export const selectIsMarketSubscribed = (state: any, marketId: string) =>
  !!state.apiSubscription.subscriptions[marketId]
export const selectMarketSubscription = (state: any, marketId: string) =>
  state.apiSubscription.subscriptions[marketId]