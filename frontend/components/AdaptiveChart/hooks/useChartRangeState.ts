import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { setSelectedRange } from '../../../lib/store/chartRangeSlice'
import { TimeRange } from '../../../lib/chart-types'

export function useChartRangeState(chartId: string) {
  const selectedRange = useAppSelector((state) => {
    console.log('📊 Redux Selector - useChartRangeState chartId:', chartId)
    console.log('📊 Redux Selector - Chart Range instances:', state.chartRange.chartInstances)
    const instance = state.chartRange.chartInstances[chartId]
    const range = instance?.selectedRange || '1H'
    console.log('📊 Redux Selector - Selected Range for chartId', chartId, ':', range)
    return range
  })
  const dispatch = useAppDispatch()

  const setRange = (range: TimeRange) => {
    console.log('🎛️ Hook Call - useChartRangeState.setRange for chartId', chartId, ':', {
      currentRange: selectedRange,
      newRange: range,
      timestamp: new Date().toISOString()
    })
    dispatch(setSelectedRange({ chartId, range }))
  }

  console.log('🎣 useChartRangeState hook - chartId:', chartId, 'selectedRange:', selectedRange)

  return {
    selectedRange,
    setRange
  }
}
