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
    dispatch(setIsFullscreen({ chartId, isFullscreen }))
  }

  const toggleFullscreenMode = () => {
    dispatch(toggleFullscreen(chartId))
  }

  const setShowButton = (show: boolean) => {
    dispatch(setShowFullscreenButton({ chartId, show }))
  }


  return {
    isFullscreen: fullscreenState.isFullscreen,
    showFullscreenButton: fullscreenState.showFullscreenButton,
    setFullscreen,
    toggleFullscreen: toggleFullscreenMode,
    setShowFullscreenButton: setShowButton
  }
}
