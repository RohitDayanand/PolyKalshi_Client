import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit'
import type { Market } from '@/types/market'

export interface SubscriptionState {
  subscribedMarkets: Market[]
  activeMarkets: Market[]
  loading: boolean
  error: string | null
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error'
}

const initialState: SubscriptionState = {
  subscribedMarkets: [],
  activeMarkets: [],
  loading: false,
  error: null,
  connectionStatus: 'disconnected',
}

// Async thunk for subscribing to a market
export const subscribeToMarket = createAsyncThunk(
  'subscription/subscribeToMarket',
  async ({ platform, market }: { platform: 'polymarket' | 'kalshi'; market: Market }) => {
    const response = await fetch('/api/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform, marketId: market.id }),
    })
    
    if (!response.ok) {
      throw new Error('Failed to subscribe to market')
    }
    
    const data = await response.json()
    return { platform, market: { ...market, platform }, subscriptionData: data }
  }
)

// Async thunk for unsubscribing from a market
export const unsubscribeFromMarket = createAsyncThunk(
  'subscription/unsubscribeFromMarket',
  async ({ marketId }: { marketId: string }) => {
    const response = await fetch('/api/unsubscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ marketId }),
    })
    
    if (!response.ok) {
      throw new Error('Failed to unsubscribe from market')
    }
    
    return { marketId }
  }
)

// Async thunk for fetching subscribed markets
export const fetchSubscribedMarkets = createAsyncThunk(
  'subscription/fetchSubscribedMarkets',
  async () => {
    const response = await fetch('/api/subscriptions')
    if (!response.ok) {
      throw new Error('Failed to fetch subscriptions')
    }
    const data = await response.json()
    return data.data
  }
)

const subscriptionSlice = createSlice({
  name: 'subscription',
  initialState,
  reducers: {
    // Set active markets for visualization
    setActiveMarkets: (state, action: PayloadAction<Market[]>) => {
      state.activeMarkets = action.payload
    },
    
    // Add market to active list
    addActiveMarket: (state, action: PayloadAction<Market>) => {
      const exists = state.activeMarkets.find(m => m.id === action.payload.id)
      if (!exists) {
        state.activeMarkets.push(action.payload)
      }
    },
    
    // Remove market from active list
    removeActiveMarket: (state, action: PayloadAction<string>) => {
      state.activeMarkets = state.activeMarkets.filter(m => m.id !== action.payload)
    },
    
    // Update subscription connection status
    setConnectionStatus: (state, action: PayloadAction<SubscriptionState['connectionStatus']>) => {
      state.connectionStatus = action.payload
    },
    
    // Update market data in subscribed markets
    updateSubscribedMarketData: (state, action: PayloadAction<{ id: string; data: Partial<Market> }>) => {
      const { id, data } = action.payload
      const marketIndex = state.subscribedMarkets.findIndex(m => m.id === id)
      if (marketIndex !== -1) {
        state.subscribedMarkets[marketIndex] = { ...state.subscribedMarkets[marketIndex], ...data }
      }
      
      // Also update in active markets
      const activeIndex = state.activeMarkets.findIndex(m => m.id === id)
      if (activeIndex !== -1) {
        state.activeMarkets[activeIndex] = { ...state.activeMarkets[activeIndex], ...data }
      }
    },
    
    // Clear all subscriptions
    clearSubscriptions: (state) => {
      state.subscribedMarkets = []
      state.activeMarkets = []
    },
    
    // Clear error
    clearError: (state) => {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      // Subscribe to market
      .addCase(subscribeToMarket.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(subscribeToMarket.fulfilled, (state, action) => {
        state.loading = false
        const { market } = action.payload
        
        // Check if already subscribed
        const exists = state.subscribedMarkets.find(m => m.id === market.id)
        if (!exists) {
          state.subscribedMarkets.push(market)
        }
      })
      .addCase(subscribeToMarket.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to subscribe to market'
      })
      
      // Unsubscribe from market
      .addCase(unsubscribeFromMarket.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(unsubscribeFromMarket.fulfilled, (state, action) => {
        state.loading = false
        const { marketId } = action.payload
        state.subscribedMarkets = state.subscribedMarkets.filter(m => m.id !== marketId)
        state.activeMarkets = state.activeMarkets.filter(m => m.id !== marketId)
      })
      .addCase(unsubscribeFromMarket.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to unsubscribe from market'
      })
      
      // Fetch subscribed markets
      .addCase(fetchSubscribedMarkets.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchSubscribedMarkets.fulfilled, (state, action) => {
        state.loading = false
        state.subscribedMarkets = action.payload
      })
      .addCase(fetchSubscribedMarkets.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to fetch subscriptions'
      })
  },
})

export const {
  setActiveMarkets,
  addActiveMarket,
  removeActiveMarket,
  setConnectionStatus,
  updateSubscribedMarketData,
  clearSubscriptions,
  clearError,
} = subscriptionSlice.actions

export default subscriptionSlice.reducer

// Selectors
export const selectSubscribedMarkets = (state: any) => 
  state.subscription.subscribedMarkets
export const selectActiveMarkets = (state: any) => 
  state.subscription.activeMarkets
export const selectSubscriptionLoading = (state: any) => 
  state.subscription.loading
export const selectSubscriptionError = (state: any) => 
  state.subscription.error
export const selectConnectionStatus = (state: any) => 
  state.subscription.connectionStatus
export const selectIsSubscribed = (state: any, marketId: string) =>
  state.subscription.subscribedMarkets.some((m: any) => m.id === marketId)
export const selectSubscribedMarketsByPlatform = (
  state: any, 
  platform: 'polymarket' | 'kalshi'
) => state.subscription.subscribedMarkets.filter((m: any) => m.platform === platform)
