import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { setIsFullscreen, toggleFullscreen, setShowFullscreenButton } from '../../../lib/store/chartFullscreenSlice'

export function useChartFullscreenState(chartId: string) {
  const fullscreenState = useAppSelector((state) => {
    console.log('📊 Redux Selector - useChartFullscreenState chartId:', chartId)
    console.log('📊 Redux Selector - Chart Fullscreen instances:', state.chartFullscreen.chartInstances)
    const instance = state.chartFullscreen.chartInstances[chartId]
    const stateObj = instance || { isFullscreen: false, showFullscreenButton: true }
    console.log('📊 Redux Selector - Fullscreen state for chartId', chartId, ':', stateObj)
    return stateObj
  })
  const dispatch = useAppDispatch()

  const setFullscreen = (isFullscreen: boolean) => {
    console.log('🎛️ Hook Call - useChartFullscreenState.setFullscreen for chartId', chartId, ':', {
      current: fullscreenState.isFullscreen,
      new: isFullscreen,
      timestamp: new Date().toISOString()
    })
    dispatch(setIsFullscreen({ chartId, isFullscreen }))
  }

  const toggleFullscreenMode = () => {
    console.log('🎛️ Hook Call - useChartFullscreenState.toggleFullscreen for chartId', chartId, ':', {
      current: fullscreenState.isFullscreen,
      willBecome: !fullscreenState.isFullscreen,
      timestamp: new Date().toISOString()
    })
    dispatch(toggleFullscreen(chartId))
  }

  const setShowButton = (show: boolean) => {
    console.log('🎛️ Hook Call - useChartFullscreenState.setShowButton for chartId', chartId, ':', {
      current: fullscreenState.showFullscreenButton,
      new: show,
      timestamp: new Date().toISOString()
    })
    dispatch(setShowFullscreenButton({ chartId, show }))
  }

  console.log('🎣 useChartFullscreenState hook - chartId:', chartId, 'state:', {
    isFullscreen: fullscreenState.isFullscreen,
    showButton: fullscreenState.showFullscreenButton
  })

  return {
    isFullscreen: fullscreenState.isFullscreen,
    showFullscreenButton: fullscreenState.showFullscreenButton,
    setFullscreen,
    toggleFullscreen: toggleFullscreenMode,
    setShowFullscreenButton: setShowButton
  }
}
