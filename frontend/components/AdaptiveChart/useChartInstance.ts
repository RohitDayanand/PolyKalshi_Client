import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import {
  createChart,
  createTextWatermark,
  LineSeries,
  IChartApi,
  ISeriesApi,
} from 'lightweight-charts'
import {
  getChartOptions,
  watermarkConfig,
  seriesOptions,
  CHART_RETRY_CONFIG,
  updateChartTimeScale,
} from '@/lib/ChartStuff/chart-config'
import {
  generateRangeData,
  generateStreamingData,
  getNextRealtimeUpdate,
} from '@/lib/ChartStuff/chart-utils'
import { ChartSeriesRefs, SeriesType, TimeRange } from '@/lib/ChartStuff/chart-types'
import type {
  Time,
  LineData,
  WhitespaceData,
} from 'lightweight-charts'


/*
Todo: Migrate chart instance in redux to chartinstanceref
*/

// Type definition for chart data points
type LinePoint = LineData<Time> | WhitespaceData<Time>

/* 🔗 global-state hooks */
//import { useChartInstanceState } from './hooks/useChartInstanceState'
import { useChartRangeState }    from './hooks/useChartRangeState'
import { useChartViewState }     from './hooks/useChartViewState'
import { useMarketSubscriptionState } from './hooks/useMarketSubscriptionState'

/* ------------------------------------------------------------------ */
/*  props — only UI-specific values stay here                          */
/* ------------------------------------------------------------------ */
interface UseChartInstanceProps {
  isVisible: boolean
  containerHeight?: number
  staticData: { yes: LinePoint[]; no: LinePoint[] }
  setStaticData: (d: { yes: LinePoint[]; no: LinePoint[] }) => void
  chartId: string
  platform?: string
  marketId?: string
}

export function useChartInstance({
  isVisible,
  containerHeight,
  staticData,
  setStaticData,
  chartId,
  platform,
  marketId
}: UseChartInstanceProps) {
  /* --------------------------------------------------------------- */
  /*  Debug: Log when platform and marketId are received           */
  /* --------------------------------------------------------------- */
  useEffect(() => {
    if (platform && marketId) {
      // Platform and market setup
    }
  }, [platform, marketId, chartId])

  /* --------------------------------------------------------------- */
  /*  global redux state - now using chartId for isolated state     */
  /* --------------------------------------------------------------- */

  const { selectedRange } = useChartRangeState(chartId)  // '1H' | '1W' | ...
  const { selectedView }  = useChartViewState(chartId)   // 'YES' | 'NO' | 'BOTH'
  const { getSubscriptionId } = useMarketSubscriptionState(chartId) // Get subscription IDs

  /* --------------------------------------------------------------- */
  /*  local refs                                             */
  /* --------------------------------------------------------------- */
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartInstanceRef = useRef<IChartApi | null>(null)
  const chartDomRef = useRef<HTMLDivElement | null>(null)
  const handleResizeRef = useRef<(() => void) | null>(null)
  const renderCount =  useRef(0)

  //this is our ref to persist access to our price series refs (legacy compatibility)
  interface PriceClassRefs {
    yes: any | null, // Legacy refs - actual price series now managed by useOverlayManager
    no: any | null,  // Legacy refs - actual price series now managed by useOverlayManager
  }

  // Legacy series ref for backward compatibility
  const seriesRef = useRef<PriceClassRefs>({
    yes: null,
    no : null,
  })

  // NEW: Price series ref - stores the main YES/NO price line series
  const priceSeriesRef = useRef<ISeriesApi<'Line'>[]>([])
  
  // NEW: Overlay series ref - stores overlay instances (moving averages, indicators, etc.)
  const overlaySeriesRef = useRef<any[]>([]) // Will store SeriesClass instances

  const streamingGeneratorRef = useRef<Generator<any, any, unknown> | null>(null)
  const streamingIntervalRef  = useRef<NodeJS.Timeout | null>(null)

  /* --------------------------------------------------------------- */
  /*  overlay manager - will be called from component level        */
  /* --------------------------------------------------------------- */
  // Overlay manager should be called from the component that uses useChartInstance

  /* --------------------------------------------------------------- */
  /*  main lifecycle (mount / unmount)                               */
  /* --------------------------------------------------------------- */
  useEffect(() => {
    renderCount.current += 1
    if (!isVisible) return

    let timeoutId: NodeJS.Timeout | null = null
    let retryCount = 0
    let chartInstance: IChartApi | null = null

    const waitForContainer = () => {
      if (chartContainerRef.current) {
        if (
          chartContainerRef.current.offsetParent !== null ||
          chartContainerRef.current.offsetWidth > 0
        ) {
          createChartInstance()
        } else if (++retryCount < CHART_RETRY_CONFIG.maxRetries) {
          timeoutId = setTimeout(waitForContainer, CHART_RETRY_CONFIG.retryDelay)
        }
        return
      }
      if (++retryCount < CHART_RETRY_CONFIG.maxRetries) {
        timeoutId = setTimeout(waitForContainer, CHART_RETRY_CONFIG.retryDelay)
      }
    }

    waitForContainer()

    return () => {
      if (timeoutId) clearTimeout(timeoutId)
      if (streamingIntervalRef.current) {
        clearInterval(streamingIntervalRef.current)
        streamingIntervalRef.current = null
      }
      if (handleResizeRef.current) {
        window.removeEventListener('resize', handleResizeRef.current)
        handleResizeRef.current = null
      }
      if (chartInstance) {
        chartInstance.remove()
        //clearInstance()                       // 🧹 clear redux state
      }
      // Clear refs
      chartInstanceRef.current = null
      chartDomRef.current = null
    }

    /* ----------------- createChartInstance ---------------------- */
    function createChartInstance() {
      if (!chartContainerRef.current) return

      const container   = chartContainerRef.current
      const chartOpts   = getChartOptions(container.clientWidth, containerHeight, selectedRange)
      const chart       = createChart(container, chartOpts)

      //assign this chart to refs
      chartInstance = chart
      chartInstanceRef.current = chart
      chartDomRef.current = container

      createTextWatermark(chart.panes()[0], watermarkConfig)
      
      // NOTE: Price series creation is now handled by useOverlayManager
      // This prevents duplication and centralizes all series management

      chart.timeScale().fitContent()
      chart.timeScale().scrollToPosition(5, false)

      /* resize handler */
      const handleResize = () => {
        if (chartContainerRef.current) {
          chart.applyOptions({
            width : chartContainerRef.current.clientWidth,
            height: containerHeight || 400,
          })
        }
      }
      handleResizeRef.current = handleResize
      window.addEventListener('resize', handleResize)

      /* update local reference */

    }
  }, [isVisible]) // runs when chart visibility changes

  /* --------------------------------------------------------------- */
  /*  view-change handler (now handled by useOverlayManager)         */
  /* --------------------------------------------------------------- */
  const handleViewChange = (newView: ReturnType<typeof useChartViewState>['selectedView']) => {
    if (!chartInstanceRef.current) return
    
    // NOTE: View changes are now handled by useOverlayManager
    // This prevents duplication and centralizes all series management
    
    // Just fit content after view change
    const chart = chartInstanceRef.current
    chart.timeScale().fitContent()
  }

  const handleRangeChange = (newRange: ReturnType<typeof useChartRangeState>['selectedRange']) => {
    if (!chartInstanceRef.current) return

    const chart = chartInstanceRef.current
    
    // NOTE: Range changes for price series are now handled by useOverlayManager
    // This prevents duplication and centralizes all series management
    
    // Just fit content after range change
    chart.timeScale().fitContent()
  }
  
  /* --------------------------------------------------------------- */
  /*  react to view changes                                          */
  /* --------------------------------------------------------------- */
  useEffect(() => {
    renderCount.current += 1
    if (chartInstanceRef.current) {
      handleViewChange(selectedView)
    }
  }, [selectedView])

  /* --------------------------------------------------------------- */
  /*  react to range changes                                         */
  /* --------------------------------------------------------------- */
  useEffect(() => {
    renderCount.current += 1
    if (chartInstanceRef.current) {
      // Update time scale formatting for the new range
      updateChartTimeScale(chartInstanceRef.current, selectedRange)
      // Handle other range change logic
      handleRangeChange(selectedRange)
    }
  }, [selectedRange])

  /* --------------------------------------------------------------- */
  /*  Resize handler for adaptive fullscreen functionality          */
  /* --------------------------------------------------------------- */
  const resizeChart = useCallback((width?: number, height?: number) => {
    if (!chartInstanceRef.current || !chartContainerRef.current) return

    const targetWidth = width || chartContainerRef.current.clientWidth
    const targetHeight = height || chartContainerRef.current.clientHeight


    try {
      chartInstanceRef.current.applyOptions({
        width: targetWidth,
        height: targetHeight
      })
    } catch (error) {
      // Error resizing chart
    }
  }, [])

  /* --------------------------------------------------------------- */
  /*  expose to callers                                              */
  /* --------------------------------------------------------------- */

  return {
    chartContainerRef,
    chartInstanceRef,
    chartDomRef,
    seriesRef,
    staticData,
    handleViewChange,
    resizeChart, // NEW: Expose resize function for adaptive behavior
  }
}
