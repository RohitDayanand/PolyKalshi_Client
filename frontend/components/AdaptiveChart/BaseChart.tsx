"use client"
/*
import { useState } from "react"
import { ChartControls } from './ChartControls'
import { useChartInstance } from './useChartInstance'
import { useOverlayManager } from './useOverlayManager'
import { useChartViewState } from './hooks/useChartViewState'
import { useChartRangeState } from './hooks/useChartRangeState'
import { useChartFullscreenState } from './hooks/useChartFullscreenState'

interface BaseChartProps {
  isVisible: boolean;
  showControls?: boolean;
  containerHeight?: number;
  className?: string;
  // Static data only for now - we'll add streaming back later
  staticData: { yes: any[], no: any[] };
  setStaticData: (data: { yes: any[], no: any[] }) => void;
}

export function BaseChart({
  isVisible,
  showControls = true,
  containerHeight,
  className = "BaseChartBuilder",
  staticData,
  setStaticData
}: BaseChartProps) {
  const { selectedView } = useChartViewState()
  const { selectedRange } = useChartRangeState()
  const { isFullscreen } = useChartFullscreenState()

  const { 
    chartContainerRef, 
    chartInstanceRef,
    handleViewChange
  } = useChartInstance({
    isVisible,
    containerHeight,
    staticData,
    setStaticData
  })

  return (
    <div className={className}>
      {showControls && (
        <ChartControls />
      )}
      
      <p className="text-xs text-slate-500 mb-2">Check browser console for debugging info</p>
      <div 
        ref={chartContainerRef} 
        className="w-full bg-slate-900 border border-slate-700 rounded mt-4" 
        style={{ 
          height: containerHeight || 400,
          minHeight: containerHeight || 400
        }}
      />
    </div>
  )
}
*/