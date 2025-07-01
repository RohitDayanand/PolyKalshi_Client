import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import { Overlay, OverlayDictionary, SeriesType, TimeRange } from '../ChartStuff/chart-types'

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
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].overlays[name] = overlay
    },
    
    removeOverlay: (state, action: PayloadAction<{ chartId: string; name: string }>) => {
      const { chartId, name } = action.payload
      
      if (state.chartInstances[chartId]) {
        delete state.chartInstances[chartId].overlays[name]
      }
    },

    // Remove overlay by matching the entire overlay object
    removeOverlayByMatch: (state, action: PayloadAction<{ chartId: string; name: string; overlay: Overlay }>) => {
      const { chartId, name, overlay } = action.payload
      
      if (!state.chartInstances[chartId]) return
      
      const existingOverlay = state.chartInstances[chartId].overlays[name]
      
      // Only remove if the overlay matches exactly
      if (existingOverlay && 
          existingOverlay.type === overlay.type &&
          existingOverlay.range === overlay.range &&
          existingOverlay.enabled === overlay.enabled &&
          existingOverlay.available === overlay.available) {
        delete state.chartInstances[chartId].overlays[name]
      } else {
      }
    },

    // Remove overlay by criteria (type + range combination)
    removeOverlayByCriteria: (state, action: PayloadAction<{ chartId: string; type: SeriesType; range: TimeRange }>) => {
      const { chartId, type, range } = action.payload
      
      if (!state.chartInstances[chartId]) return
      
      // Find and remove overlays matching the criteria
      Object.keys(state.chartInstances[chartId].overlays).forEach(name => {
        const overlay = state.chartInstances[chartId].overlays[name]
        if (overlay.type === type && overlay.range === range) {
          delete state.chartInstances[chartId].overlays[name]
        }
      })
    },
    
    updateOverlayEnabled: (state, action: PayloadAction<{ chartId: string; name: string; enabled: boolean }>) => {
      const { chartId, name, enabled } = action.payload
      
      if (state.chartInstances[chartId]?.overlays[name]) {
        state.chartInstances[chartId].overlays[name].enabled = enabled
      }
    },
    
    updateOverlayAvailable: (state, action: PayloadAction<{ chartId: string; name: string; available: boolean }>) => {
      const { chartId, name, available } = action.payload
      
      if (state.chartInstances[chartId]?.overlays[name]) {
        state.chartInstances[chartId].overlays[name].available = available
      }
    },
    
    setOverlays: (state, action: PayloadAction<{ chartId: string; overlays: OverlayDictionary }>) => {
      const { chartId, overlays } = action.payload
      
      // Initialize chart instance if it doesn't exist
      if (!state.chartInstances[chartId]) {
        state.chartInstances[chartId] = getDefaultInstanceState()
      }
      
      state.chartInstances[chartId].overlays = overlays
    },
    
    clearOverlays: (state, action: PayloadAction<string>) => {
      const chartId = action.payload
      
      if (state.chartInstances[chartId]) {
        state.chartInstances[chartId].overlays = {}
      }
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
