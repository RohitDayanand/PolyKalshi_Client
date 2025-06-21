import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { setIsFullscreen, toggleFullscreen, setShowFullscreenButton } from '../../../lib/store/chartFullscreenSlice'

export function useChartFullscreenState() {
  const fullscreenState = useAppSelector((state) => {
    console.log('📊 Redux Selector - useChartFullscreenState accessed:', {
      fullState: state,
      chartFullscreen: state.chartFullscreen,
      isFullscreen: state.chartFullscreen.isFullscreen,
      showButton: state.chartFullscreen.showFullscreenButton,
      timestamp: new Date().toISOString()
    })
    return state.chartFullscreen
  })
  const dispatch = useAppDispatch()

  const setFullscreen = (isFullscreen: boolean) => {
    console.log('🎛️ Hook Call - useChartFullscreenState.setFullscreen:', {
      current: fullscreenState.isFullscreen,
      new: isFullscreen,
      timestamp: new Date().toISOString()
    })
    dispatch(setIsFullscreen(isFullscreen))
  }

  const toggleFullscreenMode = () => {
    console.log('🎛️ Hook Call - useChartFullscreenState.toggleFullscreen:', {
      current: fullscreenState.isFullscreen,
      willBecome: !fullscreenState.isFullscreen,
      timestamp: new Date().toISOString()
    })
    dispatch(toggleFullscreen())
  }

  const setShowButton = (show: boolean) => {
    console.log('🎛️ Hook Call - useChartFullscreenState.setShowButton:', {
      current: fullscreenState.showFullscreenButton,
      new: show,
      timestamp: new Date().toISOString()
    })
    dispatch(setShowFullscreenButton(show))
  }

  console.log('🎣 useChartFullscreenState hook - Current state:', {
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
