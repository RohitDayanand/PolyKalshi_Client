import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { setSelectedRange } from '../../../lib/store/chartRangeSlice'
import { TimeRange } from '../../../lib/chart-types'

export function useChartRangeState() {
  const selectedRange = useAppSelector((state) => {
    console.log('📊 Redux Selector - useChartRangeState accessed:', {
      fullState: state,
      chartRange: state.chartRange,
      selectedRange: state.chartRange.selectedRange,
      timestamp: new Date().toISOString()
    })
    return state.chartRange.selectedRange
  })
  const dispatch = useAppDispatch()

  const setRange = (range: TimeRange) => {
    console.log('🎛️ Hook Call - useChartRangeState.setRange:', {
      currentRange: selectedRange,
      newRange: range,
      timestamp: new Date().toISOString()
    })
    dispatch(setSelectedRange(range))
  }

  console.log('🎣 useChartRangeState hook - Current selectedRange:', selectedRange)

  return {
    selectedRange,
    setRange
  }
}
