import { createSlice, PayloadAction } from '@reduxjs/toolkit'

interface ChartFullscreenState {
  isFullscreen: boolean
  showFullscreenButton: boolean
}

const initialState: ChartFullscreenState = {
  isFullscreen: false,
  showFullscreenButton: true
}

export const chartFullscreenSlice = createSlice({
  name: 'chartFullscreen',
  initialState,
  reducers: {
    setIsFullscreen: (state, action: PayloadAction<boolean>) => {
      console.log('🔄 Redux Action - chartFullscreen/setIsFullscreen:', {
        from: state.isFullscreen,
        to: action.payload,
        timestamp: new Date().toISOString()
      })
      state.isFullscreen = action.payload
    },
    toggleFullscreen: (state) => {
      console.log('🔄 Redux Action - chartFullscreen/toggleFullscreen:', {
        from: state.isFullscreen,
        to: !state.isFullscreen,
        timestamp: new Date().toISOString()
      })
      state.isFullscreen = !state.isFullscreen
    },
    setShowFullscreenButton: (state, action: PayloadAction<boolean>) => {
      console.log('🔄 Redux Action - chartFullscreen/setShowFullscreenButton:', {
        from: state.showFullscreenButton,
        to: action.payload,
        timestamp: new Date().toISOString()
      })
      state.showFullscreenButton = action.payload
    }
  }
})

export const { setIsFullscreen, toggleFullscreen, setShowFullscreenButton } = chartFullscreenSlice.actions
export default chartFullscreenSlice.reducer
