
/*
import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { setChartInstance, clearChartInstance } from '../../../lib/store/chartInstanceSlice'
import { IChartApi } from 'lightweight-charts'

export function useChartInstanceState() {
  const chartInstance = useAppSelector((state) => {
    console.log('📊 Redux Selector - useChartInstanceState accessed:', {
      fullState: state,
      chartInstance: state.chartInstance,
      chartInstanceValue: state.chartInstance.chartInstance,
      timestamp: new Date().toISOString()
    })
    return state.chartInstance.chartInstance
  })

  const dispatch = useAppDispatch()

  const setInstance = (instance: { instance: IChartApi; handleResize: () => void } | null) => {
    console.log('🎛️ Hook Call - useChartInstanceState.setInstance:', {
      newInstance: instance,
      timestamp: new Date().toISOString()
    })
    dispatch(setChartInstance(instance))
  }

  const clearInstance = () => {
    console.log('🗑️ Hook Call - useChartInstanceState.clearInstance:', {
      timestamp: new Date().toISOString()
    })
    dispatch(clearChartInstance())
  }

  console.log('🎣 useChartInstanceState hook - Current chartInstance:', chartInstance)

  return {
    chartInstance,
    setInstance,
    clearInstance
  }
}
*/