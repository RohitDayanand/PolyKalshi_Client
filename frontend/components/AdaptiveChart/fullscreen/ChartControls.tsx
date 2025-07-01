import { Maximize2 } from 'lucide-react'
import { TIME_RANGES, SERIES_VIEWS, TimeRange, SeriesView } from '@/lib/ChartStuff/chart-types'
import { useChartViewState } from '../hooks/useChartViewState'
import { useChartRangeState } from '../hooks/useChartRangeState'
import { useChartFullscreenState } from '../hooks/useChartFullscreenState'

interface ChartControlsProps {
  // All props are now optional since we use Redux for state management
  className?: string;
  chartId: string; // Required - which chart instance these controls manage
}

export function ChartControls({
  className = "",
  chartId
}: ChartControlsProps) {
  const { selectedView, setView } = useChartViewState(chartId)
  const { selectedRange, setRange } = useChartRangeState(chartId)
  const { isFullscreen, showFullscreenButton, toggleFullscreen } = useChartFullscreenState(chartId)
  
  console.log('🎛️ ChartControls - Rendered with:', {
    selectedView,
    selectedRange,
    isFullscreen,
    showFullscreenButton
  })
  
  const handleViewClick = (view: SeriesView) => {
    console.log('🔘 Button Click - View clicked:', view)
    setView(view)
  }

  const handleRangeClick = (range: TimeRange) => {
    console.log('🔘 Button Click - Range clicked:', range)
    setRange(range)
  }

  const handleFullscreenClick = () => {
    console.log('🔘 Button Click - Fullscreen clicked')
    toggleFullscreen()
  }
  
  return (
    <>
      {/* Header with Range Selector */}
      <div className="flex justify-between items-center mb-4">
        <h4 className="text-sm font-medium text-slate-400">Price Chart</h4>
        
        <div className="flex gap-2 items-center">
          {TIME_RANGES.map((range) => (
            <button
              key={range}
              onClick={() => handleRangeClick(range)}
              className={`px-3 py-1 text-sm font-medium rounded transition-colors duration-200 ${
                selectedRange === range
                  ? 'bg-blue-600 text-white'
                  : 'bg-transparent text-slate-400 hover:text-white hover:bg-slate-700'
              }`}
            >
              {range}
            </button>
          ))}
          {showFullscreenButton && (
            <button
              onClick={handleFullscreenClick}
              className="px-3 py-1 text-sm font-medium rounded transition-colors duration-200 bg-transparent text-slate-400 hover:text-white hover:bg-slate-700 ml-2"
              title="Open fullscreen chart"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
      
      {/* Series View Selector */}
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-slate-500">Series View:</span>
        <div className="flex gap-2">
          {SERIES_VIEWS.map((view) => (
            <button
              key={view}
              onClick={() => handleViewClick(view)}
              className={`px-3 py-1 text-sm font-medium rounded transition-colors duration-200 ${
                selectedView === view
                  ? 'bg-blue-600 text-white'
                  : 'bg-transparent text-slate-400 hover:text-white hover:bg-slate-700'
              }`}
            >
              {view}
            </button>
          ))}
        </div>
      </div>
    </>
  )
}