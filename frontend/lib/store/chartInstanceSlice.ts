// store/chartInstanceSlice.ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import type { IChartApi } from 'lightweight-charts'

interface ChartInstance {
    instance: IChartApi;
    handleResize: () => void;
}

interface ChartInstanceState {
    chartInstance: ChartInstance | null;
}

const initialState: ChartInstanceState = {
    chartInstance: null
}

export const chartInstanceSlice = createSlice({
    name: 'chartInstance',
    initialState,
    reducers: {
        setChartInstance(state, action: PayloadAction<ChartInstance | null>) {
            state.chartInstance = action.payload
        },
        clearChartInstance(state) {
            state.chartInstance = null
        }
    }
})

export const { setChartInstance, clearChartInstance } = chartInstanceSlice.actions
export default chartInstanceSlice.reducer
