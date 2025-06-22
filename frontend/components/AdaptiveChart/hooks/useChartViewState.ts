import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { setSelectedView } from '../../../lib/store/chartViewSlice'
import { SeriesView } from '../../../lib/chart-types'

export function useChartViewState(chartId: string) {
  const selectedView = useAppSelector((state) => {
    console.log('📊 Redux State - useChartViewState chartId:', chartId)
    console.log('📊 Redux State - Chart View instances:', state.chartView.chartInstances)
    const instance = state.chartView.chartInstances[chartId]
    const view = instance?.selectedView || 'YES'
    console.log('📊 Redux State - Selected View for chartId', chartId, ':', view)
    return view
  })
  const dispatch = useAppDispatch()

  const setView = (view: SeriesView) => {
    console.log('🔄 Redux Action - Setting view for chartId', chartId, 'to:', view)
    dispatch(setSelectedView({ chartId, view }))
    console.log('✅ Redux Action - Dispatched setSelectedView for chartId:', chartId, view)
  }

  console.log('🎣 useChartViewState hook - chartId:', chartId, 'selectedView:', selectedView)

  return {
    selectedView,
    setView
  }
}
