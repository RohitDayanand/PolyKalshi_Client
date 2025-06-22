import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import { MarketSubscription, TimeRange, SeriesType } from '../chart-types'

interface MarketSubscriptionInstanceState {
  selectedMarket: MarketSubscription
}

interface MarketSubscriptionState {
  chartInstances: Record<string, MarketSubscriptionInstanceState>
}

const getDefaultInstanceState = (): MarketSubscriptionInstanceState => ({
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
})

const initialState: MarketSubscriptionState = {
  chartInstances: {}
}

export const marketSubscriptionSlice = createSlice({
  name: 'marketSubscription',
  initialState,
  reducers: {
    setSelectedMarket: (state, action: PayloadAction<{ chartId: string; market: MarketSubscription }>) => {
      const { chartId, market } = action.payload
      console.log('🏪 Redux Reducer - marketSubscription/setSelectedMarket:', { chartId, market })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].selectedMarket = market
    },
    
    // Set subscription for specific series type and range
    setSubscription: (state, action: PayloadAction<{ chartId: string; seriesType: SeriesType; range: TimeRange; subscriptionId: string }>) => {
      const { chartId, seriesType, range, subscriptionId } = action.payload
      console.log('🏪 Redux Reducer - marketSubscription/setSubscription:', { chartId, seriesType, range, subscriptionId })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      if (seriesType === 'YES') {
        state.chartInstances[chartId].selectedMarket.yes[range] = subscriptionId
      } else {
        state.chartInstances[chartId].selectedMarket.no[range] = subscriptionId
      }
    },
    
    // Legacy methods for backward compatibility
    setYesSubscription: (state, action: PayloadAction<{ chartId: string; range: TimeRange; subscriptionId: string }>) => {
      const { chartId, range, subscriptionId } = action.payload
      console.log('🏪 Redux Reducer - marketSubscription/setYesSubscription:', { chartId, range, subscriptionId })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].selectedMarket.yes[range] = subscriptionId
    },
    
    setNoSubscription: (state, action: PayloadAction<{ chartId: string; range: TimeRange; subscriptionId: string }>) => {
      const { chartId, range, subscriptionId } = action.payload
      console.log('🏪 Redux Reducer - marketSubscription/setNoSubscription:', { chartId, range, subscriptionId })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].selectedMarket.no[range] = subscriptionId
    },
    
    // Set all subscriptions for a specific range
    setRangeSubscriptions: (state, action: PayloadAction<{ chartId: string; range: TimeRange; yesId: string; noId: string }>) => {
      const { chartId, range, yesId, noId } = action.payload
      console.log('🏪 Redux Reducer - marketSubscription/setRangeSubscriptions:', { chartId, range, yesId, noId })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].selectedMarket.yes[range] = yesId
      state.chartInstances[chartId].selectedMarket.no[range] = noId
    },
    
    initializeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      if (!state.chartInstances[chartId]) {
        console.log('🏪 Redux Reducer - marketSubscription/initializeChartInstance:', chartId)
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
    },
    
    removeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      console.log('🏪 Redux Reducer - marketSubscription/removeChartInstance:', chartId)
      delete state.chartInstances[chartId]
    }
  }
})

export const { 
  setSelectedMarket, 
  setSubscription,
  setYesSubscription, 
  setNoSubscription,
  setRangeSubscriptions,
  initializeChartInstance,
  removeChartInstance
} = marketSubscriptionSlice.actions
export default marketSubscriptionSlice.reducer
