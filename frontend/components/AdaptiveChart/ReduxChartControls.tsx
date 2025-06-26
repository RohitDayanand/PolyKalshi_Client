import { Maximize2 } from 'lucide-react'
import { TIME_RANGES, SERIES_VIEWS, TimeRange, SeriesView } from '@/lib/ChartStuff/chart-types'
import { useChartViewState } from './hooks/useChartViewState'

interface ReduxChartControlsProps {
  selectedRange: TimeRange;
  onRangeChange: (range: TimeRange) => void;
  onFullscreenToggle?: () => void;
  showFullscreenButton?: boolean;
}

export function ReduxChartControls({
  selectedRange,
  onRangeChange,
  onFullscreenToggle,
  showFullscreenButton = true
}: ReduxChartControlsProps) {
  const { selectedView, setView } = useChartViewState()

  return (
    <>
      {/* Header with Range Selector */}
      <div className="flex justify-between items-center mb-4">
        <h4 className="text-sm font-medium text-slate-400">Price Chart</h4>
        
        <div className="flex gap-2 items-center">
          {TIME_RANGES.map((range) => (
            <button
              key={range}
              onClick={() => onRangeChange(range)}
              className={`px-3 py-1 text-sm font-medium rounded transition-colors duration-200 ${
                selectedRange === range
                  ? 'bg-blue-600 text-white'
                  : 'bg-transparent text-slate-400 hover:text-white hover:bg-slate-700'
              }`}
            >
              {range}
            </button>
          ))}
          {showFullscreenButton && onFullscreenToggle && (
            <button
              onClick={onFullscreenToggle}
              className="px-3 py-1 text-sm font-medium rounded transition-colors duration-200 bg-transparent text-slate-400 hover:text-white hover:bg-slate-700 ml-2"
              title="Open fullscreen chart"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
      
      {/* Series View Selector - Now using Redux */}
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-slate-500">Series View:</span>
        <div className="flex gap-2">
          {SERIES_VIEWS.map((view) => (
            <button
              key={view}
              onClick={() => {
                console.log('🔘 Redux Series button clicked:', view)
                setView(view)
              }}
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
