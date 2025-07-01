"use client"

/**
 * ADAPTIVE CHART COMPONENT - ELEGANT SOLUTION
 * 
 * ARCHITECTURE: Single chart instance that adapts its container and layout
 * based on Redux fullscreen state, rather than switching between components.
 * 
 * BENEFITS:
 * - Preserves chart state (zoom, pan, series) across mode changes
 * - Single source of truth for chart logic
 * - Smooth transitions with CSS animations
 * - Better performance (no chart destruction/recreation)
 * - Maintains user interactions and selections
 * 
 * 
 * 
 * Notes
 * - If you want to change keybindings look at the bottom of this page 
 */

import { useEffect, useRef, useCallback, useState } from "react"
import { X, Layers } from "lucide-react"
import { useChartInstance } from '../useChartInstance'
import { useOverlayManager } from '../useOverlayManager'
import { useChartViewState } from '../hooks/useChartViewState'
import { useChartRangeState } from '../hooks/useChartRangeState'
import { useChartFullscreenState } from '../hooks/useChartFullscreenState'
import { ChartControls } from './ChartControls'
import { OverlayToggle } from './OverlayToggle'
import { TIME_RANGES, SERIES_VIEWS, TimeRange, SeriesView } from '@/lib/ChartStuff/chart-types'
import { CHART_THEME } from '@/lib/ChartStuff/chart-config'

interface AdaptiveChartProps {
  isVisible: boolean;
  showControls?: boolean;
  containerHeight?: number;
  className?: string;
  staticData: { yes: any[], no: any[] };
  setStaticData: (data: { yes: any[], no: any[] }) => void;
  chartId: string; // Required - represents which chart all of the toggles are working towards 
  platform?: string; // Platform for the selected market (e.g., 'polymarket', 'kalshi')
  marketId: string; // Market ID for the selected market
  marketTitle?: string; // Market title for display purposes
}

export function AdaptiveChart({
  isVisible,
  showControls = true,
  containerHeight = 400,
  className = "AdaptiveChart",
  staticData,
  setStaticData,
  chartId,
  platform,
  marketId,
  marketTitle
}: AdaptiveChartProps) {
  // Debug: Log when platform and marketId change
  useEffect(() => {
    if (platform && marketId) {
      // Market data received
    }
  }, [platform, marketId, marketTitle, chartId])

  // Redux state - now using chartId for isolated state
  const { selectedView, setView } = useChartViewState(chartId)
  const { selectedRange, setRange } = useChartRangeState(chartId)
  const { isFullscreen, setFullscreen } = useChartFullscreenState(chartId)

  // Overlay toggle state
  const [showOverlayToggle, setShowOverlayToggle] = useState(false)

  // Resize tracking
  const [isTransitioning, setIsTransitioning] = useState(false)
  const resizeTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  
  // Store original container dimensions using refs (persistent, no re-renders)
  const originalWidthRef = useRef<number | null>(null)
  const originalHeightRef = useRef<number | null>(null)

  // Single chart instance - this persists across fullscreen toggles
  const { 
    chartContainerRef, 
    chartInstanceRef,
    handleViewChange,
    seriesRef
  } = useChartInstance({
    isVisible,
    containerHeight: containerHeight, // Use consistent height, we'll handle resizing manually
    staticData,
    setStaticData,
    chartId,
    platform,
    marketId
  })

  // Overlay management - listens to Redux state and manages actual overlay instances
  const { 
    getActiveOverlays, 
    getOverlayInstance, 
    activeOverlayCount 
  } = useOverlayManager({ 
    chartInstanceRef,
    chartId, 
    marketId,
    platform
  })

  // Effect to capture original container dimensions when first rendered
  useEffect(() => {
    if (!isFullscreen && chartContainerRef.current && 
        (originalWidthRef.current === null || originalHeightRef.current === null)) {
      // Only capture the original dimensions once, when in embedded mode
      const rect = chartContainerRef.current.getBoundingClientRect()
      const capturedWidth = rect.width || chartContainerRef.current.clientWidth
      const capturedHeight = embeddedChartHeight // Use fixed height instead of dynamic height
      
      if (capturedWidth > 0) {
        originalWidthRef.current = capturedWidth
      }
      
      if (capturedHeight > 0) {
        originalHeightRef.current = capturedHeight
      }
    }
  }, [isFullscreen, chartContainerRef.current, containerHeight])

  // Smooth resize handler for fullscreen transitions
  const handleChartResize = useCallback(() => {
    if (!chartInstanceRef.current || !chartContainerRef.current) return

    setIsTransitioning(true)

    // Clear any existing timeout
    if (resizeTimeoutRef.current) {
      clearTimeout(resizeTimeoutRef.current)
    }

    // Debounced resize to avoid too many resize calls
    resizeTimeoutRef.current = setTimeout(() => {
      if (chartInstanceRef.current && chartContainerRef.current) {
        // Determine target dimensions based on fullscreen state
        let targetWidth: number
        let targetHeight: number

        if (isFullscreen) {
          // In fullscreen: use current container dimensions (viewport)
          const rect = chartContainerRef.current.getBoundingClientRect()
          targetWidth = rect.width || chartContainerRef.current.clientWidth
          targetHeight = rect.height || chartContainerRef.current.clientHeight
        } else {
          // In embedded mode: use container width but fixed chart height
          targetWidth = originalWidthRef.current || chartContainerRef.current.clientWidth
          targetHeight = embeddedChartHeight // Use fixed height instead of containerHeight
        }


        // Apply new dimensions to the chart
        chartInstanceRef.current.applyOptions({
          width: targetWidth,
          height: targetHeight
        })

        // Fit content after resize to maintain good UX
        chartInstanceRef.current.timeScale().fitContent()
      }
      setIsTransitioning(false)
    }, 100) // Small delay to ensure CSS transitions complete

  }, [isFullscreen, containerHeight])

  // Handle fullscreen mode changes
  useEffect(() => {
    // Manage body scroll
    if (isFullscreen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = 'unset'
    }

    // Trigger resize after fullscreen state changes
    // We need different timing for entering vs exiting fullscreen
    const resizeTimeout = setTimeout(() => {
      // Force a more aggressive resize when exiting fullscreen
      if (!isFullscreen && chartInstanceRef.current && chartContainerRef.current) {
        
        // Wait for DOM to update, then use stored original dimensions
        requestAnimationFrame(() => {
          if (chartContainerRef.current && chartInstanceRef.current) {
            // Use stored original dimensions instead of measuring during transition
            const targetWidth = originalWidthRef.current || chartContainerRef.current.clientWidth
            const targetHeight = originalHeightRef.current || containerHeight
            

            chartInstanceRef.current.applyOptions({
              width: targetWidth,
              height: targetHeight
            })

            // Fit content to ensure chart looks good in smaller container
            chartInstanceRef.current.timeScale().fitContent()
          }
        })
      } else {
        // Regular resize for entering fullscreen
        handleChartResize()
      }
    }, isFullscreen ? 50 : 150) // Longer delay when exiting fullscreen

    return () => {
      clearTimeout(resizeTimeout)
      if (!isFullscreen) {
        document.body.style.overflow = 'unset'
      }
    }
  }, [isFullscreen, handleChartResize, containerHeight])

  // Window resize handler for both fullscreen and embedded modes
  useEffect(() => {
    const handleWindowResize = () => {
      if (isFullscreen) {
        // In fullscreen, resize to new viewport dimensions
        handleChartResize()
      } else {
        // In embedded mode, update stored original dimensions if container size changed
        if (chartContainerRef.current) {
          const rect = chartContainerRef.current.getBoundingClientRect()
          const currentWidth = rect.width || chartContainerRef.current.clientWidth
          const currentHeight = embeddedChartHeight // Use fixed height
          
          let dimensionsChanged = false
          
          if (currentWidth > 0 && currentWidth !== originalWidthRef.current) {
            originalWidthRef.current = currentWidth
            dimensionsChanged = true
          }
          
          if (currentHeight > 0 && currentHeight !== originalHeightRef.current) {
            originalHeightRef.current = currentHeight
            dimensionsChanged = true
          }
          
          // Resize chart only if dimensions actually changed
          if (dimensionsChanged) {
            handleChartResize()
          }
        }
      }
    }

    window.addEventListener('resize', handleWindowResize)
    return () => window.removeEventListener('resize', handleWindowResize)
  }, [handleChartResize]) // Removed isFullscreen - only respond to actual window resizes

  // Keyboard shortcuts (only in fullscreen)
  useEffect(() => {
    if (!isFullscreen) return

    const handleKeyDown = (event: KeyboardEvent) => {
      switch (event.key) {
        case 'Escape':
          if (showOverlayToggle) {
            setShowOverlayToggle(false)
          } else {
            setFullscreen(false)
          }
          break
        case '1':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault()
            setView('YES')
          }
          break
        case '2':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault()
            setView('NO')
          }
          break
        case '3':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault()
            setView('BOTH')
          }
          break
        case 'o':
        case 'O':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault()
            setShowOverlayToggle(!showOverlayToggle)
          }
          break
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isFullscreen, setFullscreen, setView, showOverlayToggle])

  // Cleanup resize timeout on unmount
  useEffect(() => {
    return () => {
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current)
      }
    }
  }, [])

  // Dynamic styles based on fullscreen state
  const containerStyles = isFullscreen
    ? "fixed inset-0 z-50 bg-black flex flex-col transition-all duration-300 ease-in-out"
    : `${className} transition-all duration-300 ease-in-out flex flex-col`

  const chartWrapperStyles = isFullscreen
    ? "flex-1 p-4 flex flex-col"
    : "flex-1 flex flex-col"

  const chartStyles = isFullscreen
    ? "flex-1 bg-transparent border-0 rounded-lg overflow-hidden"
    : "flex-1 bg-transparent border-0 rounded mt-4"
    
  // Fixed chart height for embedded mode (independent of containerHeight)
  const embeddedChartHeight = 300 // Fixed height for the actual chart area

  return (
    <div className={containerStyles}>
      
      {/* Fullscreen Header - Only shown in fullscreen mode */}
      {isFullscreen && (
        <div className="relative flex items-center justify-between p-4 bg-[#111111] border-b border-[#232323] animate-in slide-in-from-top duration-300">
          {/* Overlay Toggle Button - Top Left */}
          <div className="absolute top-4 left-4 z-10">
            <button
              onClick={() => setShowOverlayToggle(!showOverlayToggle)}
              className={`p-2 rounded-lg transition-colors ${
                showOverlayToggle
                  ? 'bg-[#333333] text-white'
                  : 'text-[#bdbdbd] hover:text-white hover:bg-[#232323]'
              }`}
              title="Manage Overlays (Ctrl+O)"
            >
              <Layers size={20} />
            </button>
          </div>

          <div className="flex items-center gap-4 ml-16">
            <h1 className="text-xl font-semibold text-white">
              Price Chart - Fullscreen Mode
            </h1>
            <div className="flex items-center gap-2 text-sm text-[#bdbdbd]">
              <span>View: {selectedView}</span>
              <span>•</span>
              <span>Range: {selectedRange}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Time Range Selector */}
            <div className="flex gap-1 bg-[#232323] rounded-lg p-1">
              {TIME_RANGES.map((range) => (
                <button
                  key={range}
                  onClick={() => setRange(range)}
                  className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                    selectedRange === range
                      ? 'bg-[#333333] text-white'
                      : 'text-white hover:text-white hover:bg-[#2a2a2a]'
                  }`}
                >
                  {range}
                </button>
              ))}
            </div>

            {/* View Selector */}
            <div className="flex gap-1 bg-[#232323] rounded-lg p-1">
              {SERIES_VIEWS.map((view) => (
                <button
                  key={view}
                  onClick={() => setView(view)}
                  className={`px-4 py-1 text-xs font-medium rounded transition-colors ${
                    selectedView === view
                      ? 'bg-[var(--strike-green)] text-black'
                      : 'text-white hover:text-white hover:bg-[#2a2a2a]'
                  }`}
                >
                  {view}
                </button>
              ))}
            </div>

            {/* Close Button */}
            <button
              onClick={() => setFullscreen(false)}
              className="p-2 text-[#bdbdbd] hover:text-white hover:bg-[#232323] rounded-lg transition-colors"
              title="Exit Fullscreen (Esc)"
            >
              <X size={20} />
            </button>
          </div>
        </div>
      )}

      {/* Regular Controls - Only shown in embedded mode */}
      {!isFullscreen && showControls && (
        <div className="animate-in slide-in-from-top duration-300">
          <ChartControls chartId={chartId} />
        </div>
      )}

      {/* Debug info for embedded mode */}
      {!isFullscreen && (
        <p className="text-xs text-white mb-2">
          Check browser console for debugging info
          {isTransitioning && <span className="text-yellow-400 ml-2">(Transitioning...)</span>}
          {originalWidthRef.current && <span className="text-[var(--strike-green)] ml-2">Original: {Math.round(originalWidthRef.current)}×{embeddedChartHeight}px (fixed height)</span>}
          <span className="text-blue-400 ml-2">Container: {containerHeight}px</span>
        </p>
      )}

      {/* Chart Container - Adapts based on mode */}
      <div className={chartWrapperStyles}>
        <div 
          className={chartStyles}
          style={{ 
            height: isFullscreen ? '100%' : `${containerHeight}px`,
            minHeight: isFullscreen ? '500px' : 'auto'
          }}
        >
          {/* In embedded mode, chart takes fixed height regardless of container height */}
          <div 
            ref={chartContainerRef} 
            className="w-full"
            style={{ 
              height: isFullscreen ? '100%' : `${embeddedChartHeight}px`
            }}
          />
        </div>
      </div>

      {/* Fullscreen Footer - Only shown in fullscreen mode */}
      {isFullscreen && (
        <div className="p-3 bg-[#111111] border-t border-[#232323] animate-in slide-in-from-bottom duration-300">
          <div className="flex items-center justify-between text-xs text-[#bdbdbd]">
            <div className="flex items-center gap-6">
              <span>Keyboard Shortcuts:</span>
              <span><kbd className="px-1 py-0.5 bg-[#232323] text-white rounded">Esc</kbd> Exit</span>
              <span><kbd className="px-1 py-0.5 bg-[#232323] text-white rounded">Ctrl+O</kbd> Overlays</span>
              <span><kbd className="px-1 py-0.5 bg-[#232323] text-white rounded">Ctrl+1</kbd> YES</span>
              <span><kbd className="px-1 py-0.5 bg-[#232323] text-white rounded">Ctrl+2</kbd> NO</span>
              <span><kbd className="px-1 py-0.5 bg-[#232323] text-white rounded">Ctrl+3</kbd> BOTH</span>
            </div>
            <div className="flex items-center gap-2">
              <span>Series: {seriesRef?.current?.yes ? 'YES' : ''} {seriesRef?.current?.no ? 'NO' : ''}</span>
              {originalWidthRef.current && <span className="text-blue-400">Original: {Math.round(originalWidthRef.current)}×{originalHeightRef.current ? Math.round(originalHeightRef.current) : containerHeight}px</span>}
              {isTransitioning && <span className="text-yellow-400">(Resizing...)</span>}
            </div>
          </div>
        </div>
      )}

      {/* Overlay Toggle Component - Only shown when activated in fullscreen */}
      <OverlayToggle
        isVisible={isFullscreen && showOverlayToggle}
        onClose={() => setShowOverlayToggle(false)}
        chartInstance={chartInstanceRef.current}
        chartId={chartId}
      />
    </div>
  )
}
