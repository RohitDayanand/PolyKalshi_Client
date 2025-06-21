import { configureStore } from '@reduxjs/toolkit'
import chartViewReducer from './chartViewSlice'
import chartRangeReducer from './chartRangeSlice'
import chartFullscreenReducer from './chartFullscreenSlice'
import chartInstanceReducer from './chartInstanceSlice'
import marketSubscriptionReducer from './marketSubscriptionSlice'
import overlayReducer from './overlaySlice'

export const store = configureStore({
  reducer: {
    chartView: chartViewReducer,
    chartRange: chartRangeReducer,
    chartFullscreen: chartFullscreenReducer,
    chartInstance: chartInstanceReducer,
    marketSubscription: marketSubscriptionReducer,
    overlay: overlayReducer
  }
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
