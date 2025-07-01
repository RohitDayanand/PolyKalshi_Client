import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { setSelectedRange } from '../../../lib/store/chartRangeSlice'
import { TimeRange } from '../../../lib/ChartStuff/chart-types'

export function useChartRangeState(chartId: string) {
  const selectedRange = useAppSelector((state) => {
    const instance = state.chartRange.chartInstances[chartId]
    const range = instance?.selectedRange || '1H'
    return range
  })
  const dispatch = useAppDispatch()

  const setRange = (range: TimeRange) => {
    dispatch(setSelectedRange({ chartId, range }))
  }

  return {
    selectedRange,
    setRange
  }
}
