import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import { MarketSubscription, TimeRange, SeriesType } from '../chart-types'

interface MarketSubscriptionState {
  selectedMarket: MarketSubscription
}

const initialState: MarketSubscriptionState = {
  selectedMarket: {
    yes: {
      '1H': '',
      '1W': '',
      '1M': '',
      '1Y': ''
    },
    no: {
      '1H': '',
      '1W': '',
      '1M': '',
      '1Y': ''
    }
  }
}

export const marketSubscriptionSlice = createSlice({
  name: 'marketSubscription',
  initialState,
  reducers: {
    setSelectedMarket: (state, action: PayloadAction<MarketSubscription>) => {
      console.log('🏪 Redux Reducer - Previous market state:', state.selectedMarket)
      console.log('🏪 Redux Reducer - Action payload:', action.payload)
      state.selectedMarket = action.payload
      console.log('🏪 Redux Reducer - New market state:', state.selectedMarket)
    },
    
    // Set subscription for specific series type and range
    setSubscription: (state, action: PayloadAction<{ seriesType: SeriesType; range: TimeRange; subscriptionId: string }>) => {
      const { seriesType, range, subscriptionId } = action.payload
      console.log('🏪 Redux Reducer - Setting subscription:', action.payload)
      
      if (seriesType === 'YES') {
        state.selectedMarket.yes[range] = subscriptionId
      } else {
        state.selectedMarket.no[range] = subscriptionId
      }
    },
    
    // Legacy methods for backward compatibility
    setYesSubscription: (state, action: PayloadAction<{ range: TimeRange; subscriptionId: string }>) => {
      const { range, subscriptionId } = action.payload
      console.log('🏪 Redux Reducer - Setting YES subscription:', action.payload)
      state.selectedMarket.yes[range] = subscriptionId
    },
    
    setNoSubscription: (state, action: PayloadAction<{ range: TimeRange; subscriptionId: string }>) => {
      const { range, subscriptionId } = action.payload
      console.log('🏪 Redux Reducer - Setting NO subscription:', action.payload)
      state.selectedMarket.no[range] = subscriptionId
    },
    
    // Set all subscriptions for a specific range
    setRangeSubscriptions: (state, action: PayloadAction<{ range: TimeRange; yesId: string; noId: string }>) => {
      const { range, yesId, noId } = action.payload
      console.log('🏪 Redux Reducer - Setting range subscriptions:', action.payload)
      state.selectedMarket.yes[range] = yesId
      state.selectedMarket.no[range] = noId
    }
  }
})

export const { 
  setSelectedMarket, 
  setSubscription,
  setYesSubscription, 
  setNoSubscription,
  setRangeSubscriptions 
} = marketSubscriptionSlice.actions
export default marketSubscriptionSlice.reducer
