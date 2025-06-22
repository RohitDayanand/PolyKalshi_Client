
import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { setChartInstance, clearChartInstance } from '../../../lib/store/chartInstanceSlice'
import { IChartApi } from 'lightweight-charts'

export function useChartInstanceState(chartId: string) {
  const chartInstance = useAppSelector((state) => {
    console.log('📊 Redux Selector - useChartInstanceState chartId:', chartId)
    console.log('📊 Redux Selector - Chart Instance instances:', state.chartInstance.chartInstances)
    const instance = state.chartInstance.chartInstances[chartId]
    const instanceValue = instance?.chartInstance || null
    console.log('📊 Redux Selector - Chart Instance for chartId', chartId, ':', instanceValue)
    return instanceValue
  })

  const dispatch = useAppDispatch()

  const setInstance = (instance: { instance: IChartApi; handleResize: () => void } | null) => {
    console.log('🎛️ Hook Call - useChartInstanceState.setInstance for chartId', chartId, ':', {
      newInstance: instance,
      timestamp: new Date().toISOString()
    })
    dispatch(setChartInstance({ chartId, instance }))
  }

  const clearInstance = () => {
    console.log('🗑️ Hook Call - useChartInstanceState.clearInstance for chartId:', chartId, {
      timestamp: new Date().toISOString()
    })
    dispatch(clearChartInstance(chartId))
  }

  console.log('🎣 useChartInstanceState hook - chartId:', chartId, 'chartInstance:', chartInstance)

  return {
    chartInstance,
    setInstance,
    clearInstance
  }
}