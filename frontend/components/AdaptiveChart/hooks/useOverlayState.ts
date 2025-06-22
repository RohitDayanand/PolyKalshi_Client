import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { 
  setOverlay, 
  removeOverlay,
  removeOverlayByMatch,
  removeOverlayByCriteria, 
  updateOverlayEnabled, 
  updateOverlayAvailable, 
  setOverlays, 
  clearOverlays
} from '../../../lib/store/overlaySlice'
import { Overlay, OverlayDictionary, SeriesType, TimeRange } from '../../../lib/chart-types'

export function useOverlayState(chartId: string) {
  const overlays = useAppSelector((state) => {
    console.log('📊 Redux State - useOverlayState chartId:', chartId)
    console.log('📊 Redux State - Overlay instances:', state.overlay.chartInstances)
    const instance = state.overlay.chartInstances[chartId]
    const overlayDict = instance?.overlays || {}
    console.log('📊 Redux State - Overlays for chartId', chartId, ':', overlayDict)
    return overlayDict
  })
  
  const dispatch = useAppDispatch()

  const addOverlay = (name: string, overlay: Overlay) => {
    console.log('🔄 Redux Action - Adding overlay for chartId', chartId, ':', { name, overlay })
    dispatch(setOverlay({ chartId, name, overlay }))
    console.log('✅ Redux Action - Dispatched setOverlay for chartId:', chartId, { name, overlay })
  }

  const deleteOverlay = (name: string) => {
    console.log('🔄 Redux Action - Removing overlay by name for chartId', chartId, ':', name)
    dispatch(removeOverlay({ chartId, name }))
    console.log('✅ Redux Action - Dispatched removeOverlay for chartId:', chartId, name)
  }

  const deleteOverlayByMatch = (name: string, overlay: Overlay) => {
    console.log('🔄 Redux Action - Removing overlay by exact match for chartId', chartId, ':', { name, overlay })
    dispatch(removeOverlayByMatch({ chartId, name, overlay }))
    console.log('✅ Redux Action - Dispatched removeOverlayByMatch for chartId:', chartId, { name, overlay })
  }

  const deleteOverlayByCriteria = (type: SeriesType, range: TimeRange) => {
    console.log('🔄 Redux Action - Removing overlay by criteria for chartId', chartId, ':', { type, range })
    dispatch(removeOverlayByCriteria({ chartId, type, range }))
    console.log('✅ Redux Action - Dispatched removeOverlayByCriteria for chartId:', chartId, { type, range })
  }

  const toggleOverlayEnabled = (name: string, enabled: boolean) => {
    console.log('🔄 Redux Action - Toggling overlay enabled for chartId', chartId, ':', { name, enabled })
    dispatch(updateOverlayEnabled({ chartId, name, enabled }))
    console.log('✅ Redux Action - Dispatched updateOverlayEnabled for chartId:', chartId, { name, enabled })
  }

  const toggleOverlayAvailable = (name: string, available: boolean) => {
    console.log('🔄 Redux Action - Toggling overlay available for chartId', chartId, ':', { name, available })
    dispatch(updateOverlayAvailable({ chartId, name, available }))
    console.log('✅ Redux Action - Dispatched updateOverlayAvailable for chartId:', chartId, { name, available })
  }

  const setAllOverlays = (overlayDict: OverlayDictionary) => {
    console.log('🔄 Redux Action - Setting all overlays for chartId', chartId, ':', overlayDict)
    dispatch(setOverlays({ chartId, overlays: overlayDict }))
    console.log('✅ Redux Action - Dispatched setOverlays for chartId:', chartId, overlayDict)
  }

  const resetOverlays = () => {
    console.log('🔄 Redux Action - Clearing all overlays for chartId:', chartId)
    dispatch(clearOverlays(chartId))
    console.log('✅ Redux Action - Dispatched clearOverlays for chartId:', chartId)
  }

  // Helper selectors
  const getOverlay = (name: string): Overlay | undefined => {
    return overlays[name]
  }

  const getEnabledOverlays = (): OverlayDictionary => {
    const enabled: OverlayDictionary = {}
    Object.entries(overlays).forEach(([name, overlay]) => {
      if (overlay.enabled) {
        enabled[name] = overlay
      }
    })
    return enabled
  }

  const getAvailableOverlays = (): OverlayDictionary => {
    const available: OverlayDictionary = {}
    Object.entries(overlays).forEach(([name, overlay]) => {
      if (overlay.available) {
        available[name] = overlay
      }
    })
    return available
  }

  const getOverlaysByType = (type: Overlay['type']): OverlayDictionary => {
    const filtered: OverlayDictionary = {}
    Object.entries(overlays).forEach(([name, overlay]) => {
      if (overlay.type === type) {
        filtered[name] = overlay
      }
    })
    return filtered
  }

  console.log('🎣 useOverlayState hook - chartId:', chartId, 'overlays:', overlays)

  return {
    overlays,
    addOverlay,
    deleteOverlay,
    deleteOverlayByMatch,
    deleteOverlayByCriteria,
    toggleOverlayEnabled,
    toggleOverlayAvailable,
    setAllOverlays,
    resetOverlays,
    getOverlay,
    getEnabledOverlays,
    getAvailableOverlays,
    getOverlaysByType
  }
}
