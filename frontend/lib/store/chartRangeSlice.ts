import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import { TimeRange } from '../chart-types'

interface ChartRangeInstanceState {
  selectedRange: TimeRange
}

interface ChartRangeState {
  chartInstances: Record<string, ChartRangeInstanceState>
}

const initialState: ChartRangeState = {
  chartInstances: {}
}

const getDefaultInstanceState = (): ChartRangeInstanceState => ({
  selectedRange: '1H'
})

export const chartRangeSlice = createSlice({
  name: 'chartRange',
  initialState,
  reducers: {
    setSelectedRange: (state, action: PayloadAction<{ chartId: string; range: TimeRange }>) => {
      const { chartId, range } = action.payload
      console.log('🔄 Redux Action - chartRange/setSelectedRange:', {
        chartId,
        from: state.chartInstances[chartId]?.selectedRange,
        to: range,
        timestamp: new Date().toISOString()
      })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].selectedRange = range
    },
    initializeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      if (!state.chartInstances[chartId]) {
        console.log('🔄 Redux Action - chartRange/initializeChartInstance:', chartId)
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
    },
    removeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      console.log('🔄 Redux Action - chartRange/removeChartInstance:', chartId)
      delete state.chartInstances[chartId]
    }
  }
})

export const { setSelectedRange, initializeChartInstance, removeChartInstance } = chartRangeSlice.actions
export default chartRangeSlice.reducer
