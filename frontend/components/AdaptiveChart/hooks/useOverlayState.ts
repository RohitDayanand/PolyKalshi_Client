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

export function useOverlayState() {
  const overlays = useAppSelector((state) => {
    console.log('📊 Redux State - Full State:', state)
    console.log('📊 Redux State - Overlay Section:', state.overlay)
    console.log('📊 Redux State - Overlays Dictionary:', state.overlay.overlays)
    //Actual overlay returns
    return state.overlay.overlays
  })
  
  const dispatch = useAppDispatch()

  const addOverlay = (name: string, overlay: Overlay) => {
    console.log('🔄 Redux Action - Adding overlay:', { name, overlay })
    dispatch(setOverlay({ name, overlay }))
    console.log('✅ Redux Action - Dispatched setOverlay:', { name, overlay })
  }

  const deleteOverlay = (name: string) => {
    console.log('🔄 Redux Action - Removing overlay by name:', name)
    dispatch(removeOverlay(name))
    console.log('✅ Redux Action - Dispatched removeOverlay:', name)
  }

  const deleteOverlayByMatch = (name: string, overlay: Overlay) => {
    console.log('🔄 Redux Action - Removing overlay by exact match:', { name, overlay })
    dispatch(removeOverlayByMatch({ name, overlay }))
    console.log('✅ Redux Action - Dispatched removeOverlayByMatch:', { name, overlay })
  }

  const deleteOverlayByCriteria = (type: SeriesType, range: TimeRange) => {
    console.log('🔄 Redux Action - Removing overlay by criteria:', { type, range })
    dispatch(removeOverlayByCriteria({ type, range }))
    console.log('✅ Redux Action - Dispatched removeOverlayByCriteria:', { type, range })
  }

  const toggleOverlayEnabled = (name: string, enabled: boolean) => {
    console.log('🔄 Redux Action - Toggling overlay enabled:', { name, enabled })
    dispatch(updateOverlayEnabled({ name, enabled }))
    console.log('✅ Redux Action - Dispatched updateOverlayEnabled:', { name, enabled })
  }

  const toggleOverlayAvailable = (name: string, available: boolean) => {
    console.log('🔄 Redux Action - Toggling overlay available:', { name, available })
    dispatch(updateOverlayAvailable({ name, available }))
    console.log('✅ Redux Action - Dispatched updateOverlayAvailable:', { name, available })
  }

  const setAllOverlays = (overlayDict: OverlayDictionary) => {
    console.log('🔄 Redux Action - Setting all overlays:', overlayDict)
    dispatch(setOverlays(overlayDict))
    console.log('✅ Redux Action - Dispatched setOverlays:', overlayDict)
  }

  const resetOverlays = () => {
    console.log('🔄 Redux Action - Clearing all overlays')
    dispatch(clearOverlays())
    console.log('✅ Redux Action - Dispatched clearOverlays')
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

  console.log('🎣 useOverlayState hook - Current overlays:', overlays)

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
