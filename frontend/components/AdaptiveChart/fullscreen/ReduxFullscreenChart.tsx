"use client"



/**
 * REDUX-DRIVEN FULLSCREEN CHART COMPONENT
 * 
 * ARCHITECTURE DECISION: This is NOT a new chart - it's the same chart logic
 * rendered in a fullscreen overlay container.
 * 
 * KEY DESIGN PRINCIPLES:
 * 1. Uses the SAME useChartInstance hook as BaseChart
 * 2. Only renders when Redux isFullscreen = true
 * 3. Shares the same data props for synchronization
 * 4. Provides enhanced UI for large-screen experience
 * 5. Includes keyboard shortcuts for power users
 * 
 * RENDERING STRATEGY:
 * - Conditional rendering based on Redux state
 * - Fixed overlay positioning (z-50) to cover entire viewport
 * - Professional header/footer layout for fullscreen experience
 */

import { useState, useEffect, useCallback } from "react"
import { X, Settings, Maximize2, Minimize2, Layers } from "lucide-react"
import { useChartInstance } from '../useChartInstance'
import { useChartViewState } from '../hooks/useChartViewState'
import { useChartRangeState } from '../hooks/useChartRangeState'
import { useChartFullscreenState } from '../hooks/useChartFullscreenState'
import { OverlayToggle } from './OverlayToggle'
import { TIME_RANGES, SERIES_VIEWS, TimeRange, SeriesView } from '@/lib/chart-types'

interface ReduxFullscreenChartProps {
  // Data props - these come from parent component
  staticData: { yes: any[], no: any[] };
  setStaticData: (data: { yes: any[], no: any[] }) => void;
  containerHeight?: number;
}

export function ReduxFullscreenChart({
  staticData,
  setStaticData,
  containerHeight = 600
}: ReduxFullscreenChartProps) {
  // OVERLAY TOGGLE STATE: Controls visibility of overlay management panel
  const [showOverlayToggle, setShowOverlayToggle] = useState(false)
  
  // REDUX STATE HOOKS: These provide the global state for chart behavior
  // All changes here trigger re-renders and update the chart accordingly
  const { selectedView, setView } = useChartViewState()
  const { selectedRange, setRange } = useChartRangeState()
  const { isFullscreen, setFullscreen } = useChartFullscreenState()

  // CHART HOOK: This is the SAME hook used by BaseChart
  // The magic is that both charts use identical logic but different containers
  const { 
    chartContainerRef,   // DOM ref for the chart container
    handleViewChange,    // Function to update chart series (YES/NO/BOTH)
    seriesRef           // Reference to current chart series for debugging
  } = useChartInstance({
    isVisible: isFullscreen,  // Only initialize when actually in fullscreen
    containerHeight: containerHeight,
    staticData,
    setStaticData
  })

  // EVENT HANDLERS: These are wrapped in useCallback to prevent unnecessary re-renders
  // Each handler updates Redux state, which triggers chart updates via useChartInstance
  
  const handleViewClick = useCallback((view: SeriesView) => {
    console.log('🔘 ReduxFullscreenChart - View clicked:', view)
    setView(view) // Updates Redux state
    // NOTE: The actual chart update happens in useChartInstance via useEffect
  }, [setView])

  const handleRangeClick = useCallback((range: TimeRange) => {
    console.log('🔘 ReduxFullscreenChart - Range clicked:', range)
    setRange(range) // Updates Redux state
    // NOTE: This triggers data regeneration in useChartInstance
  }, [setRange])

  const handleClose = useCallback(() => {
    console.log('🔘 ReduxFullscreenChart - Closing fullscreen')
    setFullscreen(false) // This will hide this component and show BaseChart
  }, [setFullscreen])

  // KEYBOARD SHORTCUTS: Enhanced shortcuts including overlay toggle
  useEffect(() => {
    if (!isFullscreen) return

    const handleKeyDown = (event: KeyboardEvent) => {
      switch (event.key) {
        case 'Escape':
          if (showOverlayToggle) {
            setShowOverlayToggle(false)
          } else {
            handleClose()
          }
          break
        case 'o':
        case 'O':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault()
            setShowOverlayToggle(!showOverlayToggle)
          }
          break
        case '1':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault()
            handleViewClick('YES')
          }
          break
        case '2':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault()
            handleViewClick('NO')
          }
          break
        case '3':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault()
            handleViewClick('BOTH')
          }
          break
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isFullscreen, showOverlayToggle, handleClose, handleViewClick])

  // CONDITIONAL RENDERING: Only render when Redux state says we should be fullscreen
  // This is the main "switch" that toggles between embedded and fullscreen modes
  if (!isFullscreen) return null

  return (
    <div className="fixed inset-0 z-50 bg-slate-950 flex flex-col">
      {/* Header Bar */}
      <div className="flex items-center justify-between p-4 bg-slate-900 border-b border-slate-700">
        {/* Left: Title and Status */}
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold text-slate-100">
            Price Chart - Fullscreen Mode
          </h1>
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <span>View: {selectedView}</span>
            <span>•</span>
            <span>Range: {selectedRange}</span>
          </div>
        </div>

        {/* Right: Controls */}
        <div className="flex items-center gap-2">
          {/* Time Range Selector */}
          <div className="flex gap-1 bg-slate-800 rounded-lg p-1">
            {TIME_RANGES.map((range) => (
              <button
                key={range}
                onClick={() => handleRangeClick(range)}
                className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                  selectedRange === range
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:text-white hover:bg-slate-700'
                }`}
              >
                {range}
              </button>
            ))}
          </div>

          {/* View Selector */}
          <div className="flex gap-1 bg-slate-800 rounded-lg p-1">
            {SERIES_VIEWS.map((view) => (
              <button
                key={view}
                onClick={() => handleViewClick(view)}
                className={`px-4 py-1 text-xs font-medium rounded transition-colors ${
                  selectedView === view
                    ? 'bg-green-600 text-white'
                    : 'text-slate-300 hover:text-white hover:bg-slate-700'
                }`}
              >
                {view}
              </button>
            ))}
          </div>

          {/* Overlay Toggle Button */}
          <button
            onClick={() => setShowOverlayToggle(!showOverlayToggle)}
            className={`p-2 rounded-lg transition-colors ${
              showOverlayToggle
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-700'
            }`}
            title="Manage Overlays (Ctrl+O)"
          >
            <Layers size={20} />
          </button>

          {/* Close Button */}
          <button
            onClick={handleClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
            title="Exit Fullscreen (Esc)"
          >
            <X size={20} />
          </button>
        </div>
      </div>

      {/* Chart Container */}
      <div className="flex-1 p-4">
        <div className="w-full h-full bg-slate-900 border border-slate-700 rounded-lg overflow-hidden">
          <div 
            ref={chartContainerRef} 
            className="w-full h-full"
            style={{ minHeight: '500px' }}
          />
        </div>
      </div>

      {/* Footer with Keyboard Shortcuts */}
      <div className="p-3 bg-slate-900 border-t border-slate-700">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-6">
            <span>Keyboard Shortcuts:</span>
            <span><kbd className="px-1 py-0.5 bg-slate-800 rounded">Esc</kbd> Exit</span>
            <span><kbd className="px-1 py-0.5 bg-slate-800 rounded">Ctrl+O</kbd> Overlays</span>
            <span><kbd className="px-1 py-0.5 bg-slate-800 rounded">Ctrl+1</kbd> YES</span>
            <span><kbd className="px-1 py-0.5 bg-slate-800 rounded">Ctrl+2</kbd> NO</span>
            <span><kbd className="px-1 py-0.5 bg-slate-800 rounded">Ctrl+3</kbd> BOTH</span>
          </div>
          <div className="flex items-center gap-2">
            <span>Series: {seriesRef?.current?.yes ? 'YES' : ''} {seriesRef?.current?.no ? 'NO' : ''}</span>
          </div>
        </div>
      </div>

      {/* Overlay Toggle Component */}
      <OverlayToggle
        isVisible={showOverlayToggle}
        onClose={() => setShowOverlayToggle(false)}
      />
    </div>
  )
}
