import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import { SeriesView } from '../ChartStuff/chart-types'

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
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].selectedView = view
    },
    initializeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
    },
    removeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      delete state.chartInstances[chartId]
    }
  }
})

export const { setSelectedView, initializeChartInstance, removeChartInstance } = chartViewSlice.actions
export default chartViewSlice.reducer
