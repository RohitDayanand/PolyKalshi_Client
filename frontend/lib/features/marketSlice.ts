import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit'
import type { Market } from '@/types/market'

export interface MarketState {
  markets: Market[]
  loading: boolean
  error: string | null
  lastUpdated: string | null
}

const initialState: MarketState = {
  markets: [],
  loading: false,
  error: null,
  lastUpdated: null,
}

// Async thunk for fetching markets
export const fetchMarkets = createAsyncThunk(
  'market/fetchMarkets',
  async (platform: 'polymarket' | 'kalshi') => {
    const response = await fetch(`/api/markets?platform=${platform}`)
    if (!response.ok) {
      throw new Error('Failed to fetch markets')
    }
    const data = await response.json()
    return { platform, markets: data.data }
  }
)

// Async thunk for updating market data
export const updateMarketData = createAsyncThunk(
  'market/updateMarketData',
  async (marketData: Partial<Market> & { id: string }) => {
    const response = await fetch(`/api/markets/${marketData.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(marketData),
    })
    if (!response.ok) {
      throw new Error('Failed to update market')
    }
    return await response.json()
  }
)

const marketSlice = createSlice({
  name: 'market',
  initialState,
  reducers: {
    // Real-time market updates from WebSocket
    updateMarketPrice: (state, action: PayloadAction<{ id: string; price: number; timestamp: string }>) => {
      const { id, price, timestamp } = action.payload
      const market = state.markets.find(m => m.id === id)
      if (market) {
        market.price = price
        market.lastUpdated = timestamp
        state.lastUpdated = timestamp
      }
    },
    
    // Update market volume
    updateMarketVolume: (state, action: PayloadAction<{ id: string; volume: number; timestamp: string }>) => {
      const { id, volume, timestamp } = action.payload
      const market = state.markets.find(m => m.id === id)
      if (market) {
        market.volume = volume
        market.lastUpdated = timestamp
        state.lastUpdated = timestamp
      }
    },
    
    // Add new market
    addMarket: (state, action: PayloadAction<Market>) => {
      const existingMarket = state.markets.find(m => m.id === action.payload.id)
      if (!existingMarket) {
        state.markets.push(action.payload)
        state.lastUpdated = new Date().toISOString()
      }
    },
    
    // Remove market
    removeMarket: (state, action: PayloadAction<string>) => {
      state.markets = state.markets.filter(m => m.id !== action.payload)
      state.lastUpdated = new Date().toISOString()
    },
    
    // Clear all markets
    clearMarkets: (state) => {
      state.markets = []
      state.lastUpdated = new Date().toISOString()
    },
    
    // Clear error
    clearError: (state) => {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch markets
      .addCase(fetchMarkets.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchMarkets.fulfilled, (state, action) => {
        state.loading = false
        state.markets = action.payload.markets
        state.lastUpdated = new Date().toISOString()
      })
      .addCase(fetchMarkets.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to fetch markets'
      })
      
      // Update market data
      .addCase(updateMarketData.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(updateMarketData.fulfilled, (state, action) => {
        state.loading = false
        const index = state.markets.findIndex(m => m.id === action.payload.id)
        if (index !== -1) {
          state.markets[index] = { ...state.markets[index], ...action.payload }
          state.lastUpdated = new Date().toISOString()
        }
      })
      .addCase(updateMarketData.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to update market'
      })
  },
})

export const {
  updateMarketPrice,
  updateMarketVolume,
  addMarket,
  removeMarket,
  clearMarkets,
  clearError,
} = marketSlice.actions

export default marketSlice.reducer

// Selectors
export const selectMarkets = (state: any) => state.market.markets
export const selectMarketById = (state: any, id: string) =>
  state.market.markets.find((market: any) => market.id === id)
export const selectMarketsByPlatform = (state: any, platform: 'polymarket' | 'kalshi') =>
  state.market.markets.filter((market: any) => market.platform === platform)
export const selectMarketsLoading = (state: any) => state.market.loading
export const selectMarketsError = (state: any) => state.market.error
export const selectLastUpdated = (state: any) => state.market.lastUpdated
