import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import { Overlay, OverlayDictionary, SeriesType, TimeRange } from '../chart-types'

interface OverlayInstanceState {
  overlays: OverlayDictionary
}

interface OverlayState {
  chartInstances: Record<string, OverlayInstanceState>
}

const initialState: OverlayState = {
  chartInstances: {}
}

const getDefaultInstanceState = (): OverlayInstanceState => ({
  overlays: {}
})

export const overlaySlice = createSlice({
  name: 'overlay',
  initialState,
  reducers: {
    setOverlay: (state, action: PayloadAction<{ chartId: string; name: string; overlay: Overlay }>) => {
      const { chartId, name, overlay } = action.payload
      console.log('🏪 Redux Reducer - overlay/setOverlay:', { chartId, name, overlay })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].overlays[name] = overlay
    },
    
    removeOverlay: (state, action: PayloadAction<{ chartId: string; name: string }>) => {
      const { chartId, name } = action.payload
      console.log('🏪 Redux Reducer - overlay/removeOverlay:', { chartId, name })
      
      if (state.chartInstances[chartId]) {
        delete state.chartInstances[chartId].overlays[name]
      }
    },

    // Remove overlay by matching the entire overlay object
    removeOverlayByMatch: (state, action: PayloadAction<{ chartId: string; name: string; overlay: Overlay }>) => {
      const { chartId, name, overlay } = action.payload
      console.log('🏪 Redux Reducer - overlay/removeOverlayByMatch:', { chartId, name, overlay })
      
      if (!state.chartInstances[chartId]) return
      
      const existingOverlay = state.chartInstances[chartId].overlays[name]
      
      // Only remove if the overlay matches exactly
      if (existingOverlay && 
          existingOverlay.type === overlay.type &&
          existingOverlay.range === overlay.range &&
          existingOverlay.enabled === overlay.enabled &&
          existingOverlay.available === overlay.available) {
        delete state.chartInstances[chartId].overlays[name]
        console.log('🏪 Redux Reducer - Successfully removed matching overlay:', { chartId, name })
      } else {
        console.warn('🏪 Redux Reducer - Overlay mismatch, removal cancelled:', { chartId, name, expected: overlay, found: existingOverlay })
      }
    },

    // Remove overlay by criteria (type + range combination)
    removeOverlayByCriteria: (state, action: PayloadAction<{ chartId: string; type: SeriesType; range: TimeRange }>) => {
      const { chartId, type, range } = action.payload
      console.log('🏪 Redux Reducer - overlay/removeOverlayByCriteria:', { chartId, type, range })
      
      if (!state.chartInstances[chartId]) return
      
      // Find and remove overlays matching the criteria
      Object.keys(state.chartInstances[chartId].overlays).forEach(name => {
        const overlay = state.chartInstances[chartId].overlays[name]
        if (overlay.type === type && overlay.range === range) {
          delete state.chartInstances[chartId].overlays[name]
          console.log('🏪 Redux Reducer - Removed overlay matching criteria:', { chartId, name, overlay })
        }
      })
    },
    
    updateOverlayEnabled: (state, action: PayloadAction<{ chartId: string; name: string; enabled: boolean }>) => {
      const { chartId, name, enabled } = action.payload
      console.log('🏪 Redux Reducer - overlay/updateOverlayEnabled:', { chartId, name, enabled })
      
      if (state.chartInstances[chartId]?.overlays[name]) {
        state.chartInstances[chartId].overlays[name].enabled = enabled
      }
    },
    
    updateOverlayAvailable: (state, action: PayloadAction<{ chartId: string; name: string; available: boolean }>) => {
      const { chartId, name, available } = action.payload
      console.log('🏪 Redux Reducer - overlay/updateOverlayAvailable:', { chartId, name, available })
      
      if (state.chartInstances[chartId]?.overlays[name]) {
        state.chartInstances[chartId].overlays[name].available = available
      }
    },
    
    setOverlays: (state, action: PayloadAction<{ chartId: string; overlays: OverlayDictionary }>) => {
      const { chartId, overlays } = action.payload
      console.log('🏪 Redux Reducer - overlay/setOverlays:', { chartId, overlays })
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].overlays = overlays
    },
    
    clearOverlays: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      console.log('🏪 Redux Reducer - overlay/clearOverlays:', chartId)
      
      if (state.chartInstances[chartId]) {
        state.chartInstances[chartId].overlays = {}
      }
    },
    
    initializeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      if (!state.chartInstances[chartId]) {
        console.log('🏪 Redux Reducer - overlay/initializeChartInstance:', chartId)
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
    },
    
    removeChartInstance: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      console.log('🏪 Redux Reducer - overlay/removeChartInstance:', chartId)
      delete state.chartInstances[chartId]
    }
  }
})

export const { 
  setOverlay, 
  removeOverlay,
  removeOverlayByMatch,
  removeOverlayByCriteria, 
  updateOverlayEnabled, 
  updateOverlayAvailable, 
  setOverlays, 
  clearOverlays,
  initializeChartInstance,
  removeChartInstance
} = overlaySlice.actions

export default overlaySlice.reducer
