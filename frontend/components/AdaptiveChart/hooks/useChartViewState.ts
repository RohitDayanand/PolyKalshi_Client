import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { setSelectedView } from '../../../lib/store/chartViewSlice'
import { SeriesView } from '../../../lib/ChartStuff/chart-types'

export function useChartViewState(chartId: string) {
  const selectedView = useAppSelector((state) => {
    const instance = state.chartView.chartInstances[chartId]
    const view = instance?.selectedView || 'YES'
    return view
  })
  const dispatch = useAppDispatch()

  const setView = (view: SeriesView) => {
    dispatch(setSelectedView({ chartId, view }))
  }

  return {
    selectedView,
    setView
  }
}
