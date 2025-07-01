// Main chart module exports - CLEANED UP VERSION
export { BaseChart } from './BaseChart'
export { ChartControls } from './fullscreen/ChartControls'
export { AdaptiveChart } from './fullscreen/AdaptiveChart' // NEW: Elegant single-instance solution
export { useChartInstance } from './useChartInstance'

// Hooks
export { useChartViewState } from './hooks/useChartViewState'
export { useChartRangeState } from './hooks/useChartRangeState'
export { useChartFullscreenState } from './hooks/useChartFullscreenState'

// DEPRECATED - Old dual-chart approach (now removed)
// - ReduxFullscreenChart (replaced by AdaptiveChart)
// - ChartWithFullscreen (replaced by AdaptiveChart)

// LEGACY - keeping for reference
/*
export * from './core'
export * from './components'
export * from './hooks'
export * from './managers'
export * from './operations'
export * from './types'
export * from './demo'
export * from './events'
*/