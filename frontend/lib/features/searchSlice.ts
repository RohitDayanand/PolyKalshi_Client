import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit'
import type { Market } from '@/types/market'

export interface SearchState {
  query: string
  results: {
    polymarket: Market[]
    kalshi: Market[]
  }
  loading: boolean
  error: string | null
  history: string[]
}

const initialState: SearchState = {
  query: '',
  results: {
    polymarket: [],
    kalshi: [],
  },
  loading: false,
  error: null,
  history: [],
}

// Async thunk for searching markets
export const searchMarkets = createAsyncThunk(
  'search/searchMarkets',
  async ({ platform, query }: { platform: 'polymarket' | 'kalshi'; query: string }) => {
    const response = await fetch(`/api/search?platform=${platform}&query=${encodeURIComponent(query)}`)
    if (!response.ok) {
      throw new Error('Search failed')
    }
    const data = await response.json()
    return { platform, results: data.data, query }
  }
)

// Async thunk for searching both platforms
export const searchAllPlatforms = createAsyncThunk(
  'search/searchAllPlatforms',
  async (query: string) => {
    const [polymarketResponse, kalshiResponse] = await Promise.allSettled([
      fetch(`/api/search?platform=polymarket&query=${encodeURIComponent(query)}`),
      fetch(`/api/search?platform=kalshi&query=${encodeURIComponent(query)}`),
    ])

    const results = {
      polymarket: [] as Market[],
      kalshi: [] as Market[],
    }

    if (polymarketResponse.status === 'fulfilled' && polymarketResponse.value.ok) {
      const data = await polymarketResponse.value.json()
      results.polymarket = data.data
    }

    if (kalshiResponse.status === 'fulfilled' && kalshiResponse.value.ok) {
      const data = await kalshiResponse.value.json()
      results.kalshi = data.data
    }

    return { results, query }
  }
)

const searchSlice = createSlice({
  name: 'search',
  initialState,
  reducers: {
    setQuery: (state, action: PayloadAction<string>) => {
      state.query = action.payload
    },
    
    clearResults: (state) => {
      state.results = {
        polymarket: [],
        kalshi: [],
      }
      state.error = null
    },
    
    clearError: (state) => {
      state.error = null
    },
    
    addToHistory: (state, action: PayloadAction<string>) => {
      const query = action.payload.trim()
      if (query && !state.history.includes(query)) {
        state.history.unshift(query)
        // Keep only last 10 searches
        if (state.history.length > 10) {
          state.history = state.history.slice(0, 10)
        }
      }
    },
    
    clearHistory: (state) => {
      state.history = []
    },
    
    removeFromHistory: (state, action: PayloadAction<string>) => {
      state.history = state.history.filter(item => item !== action.payload)
    },
  },
  extraReducers: (builder) => {
    builder
      // Single platform search
      .addCase(searchMarkets.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(searchMarkets.fulfilled, (state, action) => {
        state.loading = false
        const { platform, results, query } = action.payload
        state.results[platform] = results
        state.query = query
        
        // Add to search history
        if (query.trim() && !state.history.includes(query.trim())) {
          state.history.unshift(query.trim())
          if (state.history.length > 10) {
            state.history = state.history.slice(0, 10)
          }
        }
      })
      .addCase(searchMarkets.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Search failed'
      })
      
      // All platforms search
      .addCase(searchAllPlatforms.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(searchAllPlatforms.fulfilled, (state, action) => {
        state.loading = false
        const { results, query } = action.payload
        state.results = results
        state.query = query
        
        // Add to search history
        if (query.trim() && !state.history.includes(query.trim())) {
          state.history.unshift(query.trim())
          if (state.history.length > 10) {
            state.history = state.history.slice(0, 10)
          }
        }
      })
      .addCase(searchAllPlatforms.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Search failed'
      })
  },
})

export const {
  setQuery,
  clearResults,
  clearError,
  addToHistory,
  clearHistory,
  removeFromHistory,
} = searchSlice.actions

export default searchSlice.reducer

// Selectors
export const selectSearchQuery = (state: any) => state.search.query
export const selectSearchResults = (state: any) => state.search.results
export const selectSearchLoading = (state: any) => state.search.loading
export const selectSearchError = (state: any) => state.search.error
export const selectSearchHistory = (state: any) => state.search.history
export const selectPolymarketResults = (state: any) => state.search.results.polymarket
export const selectKalshiResults = (state: any) => state.search.results.kalshi
