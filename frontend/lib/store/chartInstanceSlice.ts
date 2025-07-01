// store/chartInstanceSlice.ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import type { IChartApi } from 'lightweight-charts'

interface ChartInstance {
    instance: IChartApi;
    handleResize: () => void;
}

interface ChartInstanceRecord {
    chartInstance: ChartInstance | null;
}

interface ChartInstanceState {
    chartInstances: Record<string, ChartInstanceRecord>;
}

const initialState: ChartInstanceState = {
    chartInstances: {}
}

const getDefaultInstanceState = (): ChartInstanceRecord => ({
    chartInstance: null
})

export const chartInstanceSlice = createSlice({
    name: 'chartInstance',
    initialState,
    reducers: {
        setChartInstance(state, action: PayloadAction<{ chartId: string; instance: ChartInstance | null }>) {
            const { chartId, instance } = action.payload
            console.log('🏪 Redux Reducer - chartInstance/setChartInstance:', { chartId, hasInstance: !!instance })
            
            // Initialize chart instance if it doesn't exist
            if (!state.chartInstances[chartId]) {
                state.chartInstances[chartId] = getDefaultInstanceState()
            }
            
            state.chartInstances[chartId].chartInstance = instance
        },
        clearChartInstance(state, action: PayloadAction<string>) {
            const chartId = action.payload
            console.log('🏪 Redux Reducer - chartInstance/clearChartInstance:', chartId)
            
            if (state.chartInstances[chartId]) {
                state.chartInstances[chartId].chartInstance = null
            }
        },
        initializeChartInstance: (state, action: PayloadAction<string>) => {
            const chartId = action.payload
            if (!state.chartInstances[chartId]) {
                console.log('🏪 Redux Reducer - chartInstance/initializeChartInstance:', chartId)
                state.chartInstances[chartId] = getDefaultInstanceState()
            }
        },
        removeChartInstance: (state, action: PayloadAction<string>) => {
            const chartId = action.payload
            console.log('🏪 Redux Reducer - chartInstance/removeChartInstance:', chartId)
            delete state.chartInstances[chartId]
        }
    }
})

export const { setChartInstance, clearChartInstance, initializeChartInstance, removeChartInstance } = chartInstanceSlice.actions
export default chartInstanceSlice.reducer
