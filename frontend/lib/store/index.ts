import { configureStore } from '@reduxjs/toolkit'
import chartViewReducer from './chartViewSlice'
import chartRangeReducer from './chartRangeSlice'
import chartFullscreenReducer from './chartFullscreenSlice'
import chartInstanceReducer from './chartInstanceSlice'
import marketSubscriptionReducer from './marketSubscriptionSlice'
import overlayReducer from './overlaySlice'
import websocketReducer from './websocketSlice'
import apiSubscriptionReducer from './apiSubscriptionSlice'
import { websocketMiddleware, initializeWebSocket } from './websocketMiddleware'
import { rxjsSubscriptionMiddleware } from './rxjsSubscriptionMiddleware'

// Known chart instances for dual market visualization
const KNOWN_CHART_IDS = ['market-1', 'market-2', 'comparison'] as const

// Create preloaded state with all known chart instances
const createPreloadedState = () => {
  const preloadedState = {
    chartView: {
      chartInstances: Object.fromEntries(
        KNOWN_CHART_IDS.map(chartId => [chartId, { selectedView: 'YES' as const }])
      )
    },
    chartRange: {
      chartInstances: Object.fromEntries(
        KNOWN_CHART_IDS.map(chartId => [chartId, { selectedRange: '1H' as const }])
      )
    },
    chartFullscreen: {
      chartInstances: Object.fromEntries(
        KNOWN_CHART_IDS.map(chartId => [chartId, { 
          isFullscreen: false, 
          showFullscreenButton: true 
        }])
      )
    },
    chartInstance: {
      chartInstances: Object.fromEntries(
        KNOWN_CHART_IDS.map(chartId => [chartId, { chartInstance: null }])
      )
    },
    marketSubscription: {
      chartInstances: Object.fromEntries(
        KNOWN_CHART_IDS.map(chartId => [chartId, { 
          selectedMarket: {
            yes: { '1H': '', '1W': '', '1M': '', '1Y': '' },
            no: { '1H': '', '1W': '', '1M': '', '1Y': '' }
          }
        }])
      )
    },
    overlay: {
      chartInstances: Object.fromEntries(
        KNOWN_CHART_IDS.map(chartId => [chartId, { overlays: {} }])
      )
    }
  }
  
  console.log('🚀 Redux Store - Eager initialization complete for chartIds:', KNOWN_CHART_IDS)
  console.log('🚀 Redux Store - Preloaded state:', preloadedState)
  
  return preloadedState
}

export const store = configureStore({
  reducer: {
    chartView: chartViewReducer,
    chartRange: chartRangeReducer,
    chartFullscreen: chartFullscreenReducer,
    chartInstance: chartInstanceReducer,
    marketSubscription: marketSubscriptionReducer,
    overlay: overlayReducer,
    websocket: websocketReducer,
    apiSubscription: apiSubscriptionReducer
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(websocketMiddleware, rxjsSubscriptionMiddleware),
  preloadedState: createPreloadedState()
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch

// Initialize WebSocket connection
initializeWebSocket(store)
