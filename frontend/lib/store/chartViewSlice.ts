import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import { SeriesView } from '../chart-types'

interface ChartViewInstanceState {
  selectedView: SeriesView
}

interface ChartViewState {
  chartInstances: Record<string, ChartViewInstanceState>
}

const initialState: ChartViewState = {
  chartInstances: {}
}

const getDefaultInstanceState = (): ChartViewInstanceState => ({
  selectedView: 'YES'
})

export const chartViewSlice = createSlice({
  name: 'chartView',
  initialState,
  reducers: {
    setSelectedView: (state, action: PayloadAction<{ chartId: string; view: SeriesView }>) => {
      const { chartId, view } = action.payload
      console.log('🏪 Redux Reducer - chartView/setSelectedView:', {
        chartId,
        previousView: state.chartInstances[chartId]?.selectedView,
        newView: view,
        timestamp: new Date().toISOString()
      })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].selectedView = view
    },
    initializeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      if (!state.chartInstances[chartId]) {
        console.log('🏪 Redux Reducer - chartView/initializeChartInstance:', chartId)
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
    },
    removeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      console.log('🏪 Redux Reducer - chartView/removeChartInstance:', chartId)
      delete state.chartInstances[chartId]
    }
  }
})

export const { setSelectedView, initializeChartInstance, removeChartInstance } = chartViewSlice.actions
export default chartViewSlice.reducer
