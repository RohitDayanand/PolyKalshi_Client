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
import { Overlay, OverlayDictionary, SeriesType, TimeRange } from '../../../lib/ChartStuff/chart-types'

export function useOverlayState(chartId: string) {
  const overlays = useAppSelector((state) => {
    const instance = state.overlay.chartInstances[chartId]
    const overlayDict = instance?.overlays || {}
    return overlayDict
  })
  
  const dispatch = useAppDispatch()

  const addOverlay = (name: string, overlay: Overlay) => {
    dispatch(setOverlay({ chartId, name, overlay }))
  }

  const deleteOverlay = (name: string) => {
    dispatch(removeOverlay({ chartId, name }))
  }

  const deleteOverlayByMatch = (name: string, overlay: Overlay) => {
    dispatch(removeOverlayByMatch({ chartId, name, overlay }))
  }

  const deleteOverlayByCriteria = (type: SeriesType, range: TimeRange) => {
    dispatch(removeOverlayByCriteria({ chartId, type, range }))
  }

  const toggleOverlayEnabled = (name: string, enabled: boolean) => {
    dispatch(updateOverlayEnabled({ chartId, name, enabled }))
  }

  const toggleOverlayAvailable = (name: string, available: boolean) => {
    dispatch(updateOverlayAvailable({ chartId, name, available }))
  }

  const setAllOverlays = (overlayDict: OverlayDictionary) => {
    dispatch(setOverlays({ chartId, overlays: overlayDict }))
  }

  const resetOverlays = () => {
    dispatch(clearOverlays(chartId))
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
