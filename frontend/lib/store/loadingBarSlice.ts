import { createSlice, PayloadAction } from '@reduxjs/toolkit'

interface LoadingBarState {
  isLoading: boolean
  marketId?: string
  platform?: 'polymarket' | 'kalshi'
}

const initialState: LoadingBarState = {
  isLoading: false,
  marketId: undefined,
  platform: undefined
}

const loadingBarSlice = createSlice({
  name: 'loadingBar',
  initialState,
  reducers: {
    startLoading: (state, action: PayloadAction<{ marketId: string; platform: 'polymarket' | 'kalshi' }>) => {
      state.isLoading = true
      state.marketId = action.payload.marketId
      state.platform = action.payload.platform
    },
    stopLoading: (state) => {
      state.isLoading = false
      state.marketId = undefined
      state.platform = undefined
    }
  }
})

export const { startLoading, stopLoading } = loadingBarSlice.actions

export const selectIsLoadingBar = (state: { loadingBar: LoadingBarState }) => state.loadingBar.isLoading
export const selectLoadingBarMarket = (state: { loadingBar: LoadingBarState }) => ({
  marketId: state.loadingBar.marketId,
  platform: state.loadingBar.platform
})

export default loadingBarSlice.reducer