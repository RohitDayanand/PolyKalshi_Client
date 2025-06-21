import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import { Overlay, OverlayDictionary, SeriesType, TimeRange } from '../chart-types'

interface OverlayState {
  overlays: OverlayDictionary
}

const initialState: OverlayState = {
  overlays: {}
}

export const overlaySlice = createSlice({
  name: 'overlay',
  initialState,
  reducers: {
    setOverlay: (state, action: PayloadAction<{ name: string; overlay: Overlay }>) => {
      console.log('🏪 Redux Reducer - Previous overlay state:', state.overlays)
      console.log('🏪 Redux Reducer - Setting overlay:', action.payload)
      state.overlays[action.payload.name] = action.payload.overlay
      console.log('🏪 Redux Reducer - New overlay state:', state.overlays)
    },
    
    removeOverlay: (state, action: PayloadAction<string>) => {
      console.log('🏪 Redux Reducer - Removing overlay by name:', action.payload)
      delete state.overlays[action.payload]
      console.log('🏪 Redux Reducer - Overlay state after removal:', state.overlays)
    },

    // Remove overlay by matching the entire overlay object
    removeOverlayByMatch: (state, action: PayloadAction<{ name: string; overlay: Overlay }>) => {
      console.log('🏪 Redux Reducer - Removing overlay by match:', action.payload)
      const { name, overlay } = action.payload
      const existingOverlay = state.overlays[name]
      
      // Only remove if the overlay matches exactly
      if (existingOverlay && 
          existingOverlay.type === overlay.type &&
          existingOverlay.range === overlay.range &&
          existingOverlay.enabled === overlay.enabled &&
          existingOverlay.available === overlay.available) {
        delete state.overlays[name]
        console.log('🏪 Redux Reducer - Successfully removed matching overlay:', name)
      } else {
        console.warn('🏪 Redux Reducer - Overlay mismatch, removal cancelled:', { name, expected: overlay, found: existingOverlay })
      }
    },

    // Remove overlay by criteria (type + range combination)
    removeOverlayByCriteria: (state, action: PayloadAction<{ type: SeriesType; range: TimeRange }>) => {
      console.log('🏪 Redux Reducer - Removing overlay by criteria:', action.payload)
      const { type, range } = action.payload
      
      // Find and remove overlays matching the criteria
      Object.keys(state.overlays).forEach(name => {
        const overlay = state.overlays[name]
        if (overlay.type === type && overlay.range === range) {
          delete state.overlays[name]
          console.log('🏪 Redux Reducer - Removed overlay matching criteria:', name, overlay)
        }
      })
    },
    
    updateOverlayEnabled: (state, action: PayloadAction<{ name: string; enabled: boolean }>) => {
      console.log('🏪 Redux Reducer - Updating overlay enabled status:', action.payload)
      if (state.overlays[action.payload.name]) {
        state.overlays[action.payload.name].enabled = action.payload.enabled
      }
    },
    
    updateOverlayAvailable: (state, action: PayloadAction<{ name: string; available: boolean }>) => {
      console.log('🏪 Redux Reducer - Updating overlay available status:', action.payload)
      if (state.overlays[action.payload.name]) {
        state.overlays[action.payload.name].available = action.payload.available
      }
    },
    
    setOverlays: (state, action: PayloadAction<OverlayDictionary>) => {
      console.log('🏪 Redux Reducer - Setting all overlays:', action.payload)
      state.overlays = action.payload
    },
    
    clearOverlays: (state) => {
      console.log('🏪 Redux Reducer - Clearing all overlays')
      state.overlays = {}
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
  clearOverlays 
} = overlaySlice.actions

export default overlaySlice.reducer
