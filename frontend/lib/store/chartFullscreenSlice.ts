import { createSlice, PayloadAction } from '@reduxjs/toolkit'

interface ChartFullscreenInstanceState {
  isFullscreen: boolean
  showFullscreenButton: boolean
}

interface ChartFullscreenState {
  chartInstances: Record<string, ChartFullscreenInstanceState>
}

const initialState: ChartFullscreenState = {
  chartInstances: {}
}

const getDefaultInstanceState = (): ChartFullscreenInstanceState => ({
  isFullscreen: false,
  showFullscreenButton: true
})

export const chartFullscreenSlice = createSlice({
  name: 'chartFullscreen',
  initialState,
  reducers: {
    setIsFullscreen: (state, action: PayloadAction<{ chartId: string; isFullscreen: boolean }>) => {
      const { chartId, isFullscreen } = action.payload
      console.log('🔄 Redux Action - chartFullscreen/setIsFullscreen:', {
        chartId,
        from: state.chartInstances[chartId]?.isFullscreen,
        to: isFullscreen,
        timestamp: new Date().toISOString()
      })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].isFullscreen = isFullscreen
    },
    toggleFullscreen: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      const currentValue = state.chartInstances[chartId].isFullscreen
      console.log('🔄 Redux Action - chartFullscreen/toggleFullscreen:', {
        chartId,
        from: currentValue,
        to: !currentValue,
        timestamp: new Date().toISOString()
      })
      state.chartInstances[chartId].isFullscreen = !currentValue
    },
    setShowFullscreenButton: (state, action: PayloadAction<{ chartId: string; show: boolean }>) => {
      const { chartId, show } = action.payload
      console.log('🔄 Redux Action - chartFullscreen/setShowFullscreenButton:', {
        chartId,
        from: state.chartInstances[chartId]?.showFullscreenButton,
        to: show,
        timestamp: new Date().toISOString()
      })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].showFullscreenButton = show
    },
    initializeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      if (!state.chartInstances[chartId]) {
        console.log('🔄 Redux Action - chartFullscreen/initializeChartInstance:', chartId)
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
    },
    removeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      console.log('🔄 Redux Action - chartFullscreen/removeChartInstance:', chartId)
      delete state.chartInstances[chartId]
    }
  }
})

export const { setIsFullscreen, toggleFullscreen, setShowFullscreenButton, initializeChartInstance, removeChartInstance } = chartFullscreenSlice.actions
export default chartFullscreenSlice.reducer
