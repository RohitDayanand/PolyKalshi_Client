import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { setSelectedView } from '../../../lib/store/chartViewSlice'
import { SeriesView } from '../../../lib/chart-types'

export function useChartViewState() {
  const selectedView = useAppSelector((state) => {
    console.log('📊 Redux State - Full State:', state)
    console.log('📊 Redux State - Chart View:', state.chartView)
    console.log('📊 Redux State - Selected View:', state.chartView.selectedView)
    return state.chartView.selectedView
  })
  const dispatch = useAppDispatch()

  const setView = (view: SeriesView) => {
    console.log('🔄 Redux Action - Setting view to:', view)
    dispatch(setSelectedView(view))
    console.log('✅ Redux Action - Dispatched setSelectedView:', view)
  }

  console.log('🎣 useChartViewState hook - Current selectedView:', selectedView)

  return {
    selectedView,
    setView
  }
}
