"use client"

/**
 * OVERLAY TOGGLE COMPONENT
 * 
 * ARCHITECTURE DESIGN:
 * This component provides a search-enabled overlay management interface for fullscreen charts.
 * 
 * KEY DESIGN PRINCIPLES:
 * 1. On-demand overlay creation - overlays are instantiated when enabled, not pre-created
 * 2. Fuzzy search integration - "ma" matches "moving_average", "vol" matches "volume"
 * 3. Availability filtering - hides incompatible overlays (e.g., NO overlays when viewing YES)
 * 4. Multi-select interface - checkbox-based selection with bulk enable/disable
 * 5. Redux state synchronization - integrates with existing overlay store
 * 
 * OVERLAY CREATION STRATEGY:
 * - Overlays are created dynamically when user enables them
 * - BaseClass.setRange() allows switching ranges without recreation
 * - Redux tracks enabled/available state for UI consistency
 * - Search operates on metadata, not actual overlay instances
 * 
 * FILTERING LOGIC:
 * - Current SeriesView (YES/NO/BOTH) determines available overlays
 * - Search string filters by overlay name, description, and fuzzy matches
 * - Disabled overlays remain visible but grayed out for user awareness
 */

import { useState, useMemo, useCallback, useEffect } from "react"
import { Search, Settings, X, CheckSquare, Square, Plus, Minus } from "lucide-react"
import { SeriesType, TimeRange, SeriesView } from '@/lib/chart-types'
import { OVERLAY_REGISTRY, type OverlayMetadata } from '@/lib/overlay-registry'
import { useOverlayState } from '../hooks/useOverlayState'
import { useChartViewState } from '../hooks/useChartViewState'
import { useChartRangeState } from '../hooks/useChartRangeState'
import { IChartApi } from 'lightweight-charts'

interface OverlayToggleProps {
    isVisible: boolean;
    onClose: () => void;
    className?: string;
    chartInstance: IChartApi | null;
    chartId: string;
}

export function OverlayToggle({
  isVisible,
  onClose,
  chartInstance,
  chartId,
  className = "OverlayToggle"
}: OverlayToggleProps) {
  // STATE HOOKS
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedOverlays, setSelectedOverlays] = useState<Set<string>>(new Set())
  
  // REDUX HOOKS: Chart state and overlay management - now using chartId
  const { selectedView } = useChartViewState(chartId)
  const { selectedRange } = useChartRangeState(chartId)
  const { 
    overlays, 
    addOverlay, 
    deleteOverlay, 
    toggleOverlayEnabled,
    toggleOverlayAvailable 
  } = useOverlayState(chartId)

  // FUZZY SEARCH IMPLEMENTATION
  const fuzzySearch = useCallback((query: string, target: string, keywords: string[]): boolean => {
    if (!query) return true;
    
    const searchLower = query.toLowerCase();
    const targetLower = target.toLowerCase();
    
    // Direct match in name or display name
    if (targetLower.includes(searchLower)) return true;
    
    // Keyword matching for fuzzy search
    const matchingKeywords = keywords.some(keyword => 
      keyword.toLowerCase().includes(searchLower) || 
      searchLower.includes(keyword.toLowerCase())
    );
    
    if (matchingKeywords) return true;
    
    // Character sequence matching (e.g., "ma" matches "moving average")
    const chars = searchLower.split('');
    let charIndex = 0;
    
    for (let i = 0; i < targetLower.length && charIndex < chars.length; i++) {
      if (targetLower[i] === chars[charIndex]) {
        charIndex++;
      }
    }
    
    return charIndex === chars.length;
  }, [])

  // OVERLAY FILTERING LOGIC
  const filteredOverlays = useMemo(() => {
    return OVERLAY_REGISTRY.filter(overlay => {
      // 1. Search query filtering
      if (!fuzzySearch(searchQuery, overlay.displayName, overlay.keywords)) {
        return false;
      }
      
      // 2. Compatibility filtering based on current view
      if (selectedView !== 'BOTH') {
        const seriesType = selectedView as SeriesType;
        if (!overlay.compatibleWith.includes(seriesType)) {
          return false;
        }
      }
      
      // 3. Timeframe requirements
      if (overlay.requiresTimeframe && !overlay.requiresTimeframe.includes(selectedRange)) {
        return false;
      }
      
      return true;
    });
  }, [searchQuery, selectedView, selectedRange, fuzzySearch])

  // OVERLAY STATE HELPERS
  const getOverlayState = useCallback((overlayName: string) => {
    const overlayKey = overlayName;
    return overlays[overlayKey] || null;
  }, [overlays])

  const isOverlayEnabled = useCallback((overlayName: string): boolean => {
    const state = getOverlayState(overlayName);
    return state?.enabled || false;
  }, [getOverlayState])

  const isOverlayAvailable = useCallback((overlayName: string): boolean => {
    const state = getOverlayState(overlayName);
    return state?.available !== false; // Default to available if not set
  }, [getOverlayState])

  // OVERLAY ACTIONS
  const handleOverlayToggle = useCallback((overlayName: string) => {
    const overlayKey = overlayName;
    const currentState = getOverlayState(overlayName);
    
    if (currentState?.enabled) {
      // Disable overlay
      toggleOverlayEnabled(overlayKey, false);
      console.log('🎛️ OverlayToggle - Disabled overlay:', overlayKey);
    } else {
      // Enable overlay (create if doesn't exist)
      if (!currentState) {
        // Create new overlay state
        const seriesType = selectedView === 'BOTH' ? 'YES' : selectedView as SeriesType;
        addOverlay(overlayKey, {
          type: seriesType,
          range: selectedRange,
          enabled: true,
          available: true
        });
        console.log('🎛️ OverlayToggle - Created and enabled overlay:', overlayKey);
      } else {
        // Just enable existing overlay
        toggleOverlayEnabled(overlayKey, true);
        console.log('🎛️ OverlayToggle - Enabled existing overlay:', overlayKey);
      }
    }
  }, [selectedRange, selectedView, getOverlayState, toggleOverlayEnabled, addOverlay])

  // MULTI-SELECT ACTIONS
  const handleSelectOverlay = useCallback((overlayName: string) => {
    const newSelection = new Set(selectedOverlays);
    if (newSelection.has(overlayName)) {
      newSelection.delete(overlayName);
    } else {
      newSelection.add(overlayName);
    }
    setSelectedOverlays(newSelection);
  }, [selectedOverlays])

  const handleBulkEnable = useCallback(() => {
    selectedOverlays.forEach(overlayName => {
      if (!isOverlayEnabled(overlayName)) {
        handleOverlayToggle(overlayName);
      }
    });
    setSelectedOverlays(new Set()); // Clear selection after bulk action
  }, [selectedOverlays, isOverlayEnabled, handleOverlayToggle])

  const handleBulkDisable = useCallback(() => {
    selectedOverlays.forEach(overlayName => {
      if (isOverlayEnabled(overlayName)) {
        handleOverlayToggle(overlayName);
      }
    });
    setSelectedOverlays(new Set()); // Clear selection after bulk action
  }, [selectedOverlays, isOverlayEnabled, handleOverlayToggle])

  // KEYBOARD SHORTCUTS
  useEffect(() => {
    if (!isVisible) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'Enter' && selectedOverlays.size > 0) {
        e.preventDefault();
        handleBulkEnable();
      } else if (e.key === 'Delete' && selectedOverlays.size > 0) {
        e.preventDefault();
        handleBulkDisable();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isVisible, onClose, selectedOverlays.size, handleBulkEnable, handleBulkDisable])

  // RENDER GUARD
  if (!isVisible) return null;

  return (
    <div className={`${className} fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50`}>
      <div className="bg-slate-900 rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col border border-slate-700">
        {/* HEADER */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-slate-100">Chart Overlays</h2>
            <span className="text-sm text-slate-400">({selectedRange})</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* SEARCH BAR */}
        <div className="p-4 border-b border-slate-700">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search overlays... (e.g., 'ma' for moving average)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              autoFocus
            />
          </div>
        </div>

        {/* BULK ACTIONS */}
        {selectedOverlays.size > 0 && (
          <div className="p-4 bg-slate-800 border-b border-slate-700 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-200">
              {selectedOverlays.size} overlay{selectedOverlays.size !== 1 ? 's' : ''} selected
            </span>
            <div className="flex gap-2">
              <button
                onClick={handleBulkEnable}
                className="flex items-center gap-1 px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700 transition-colors"
              >
                <Plus className="w-3 h-3" />
                Enable All
              </button>
              <button
                onClick={handleBulkDisable}
                className="flex items-center gap-1 px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 transition-colors"
              >
                <Minus className="w-3 h-3" />
                Disable All
              </button>
            </div>
          </div>
        )}

        {/* OVERLAY LIST */}
        <div className="flex-1 overflow-y-auto">
          {filteredOverlays.length === 0 ? (
            <div className="p-8 text-center text-slate-400">
              <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No overlays found matching "{searchQuery}"</p>
              <p className="text-sm mt-1 text-slate-500">Try searching for "ma", "rsi", or "volume"</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700">
              {filteredOverlays.map((overlay) => {
                const isEnabled = isOverlayEnabled(overlay.name);
                const isAvailable = isOverlayAvailable(overlay.name);
                const isSelected = selectedOverlays.has(overlay.name);

                return (
                  <div
                    key={overlay.name}
                    className={`p-4 hover:bg-slate-800 cursor-pointer transition-colors ${
                      !isAvailable ? 'opacity-50' : ''
                    } ${isSelected ? 'bg-blue-900/50 border-l-2 border-blue-500' : ''}`}
                    onClick={() => handleSelectOverlay(overlay.name)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {/* SELECTION CHECKBOX */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectOverlay(overlay.name);
                          }}
                          className="text-slate-400 hover:text-slate-200"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-blue-400" />
                          ) : (
                            <Square className="w-4 h-4" />
                          )}
                        </button>

                        {/* OVERLAY INFO */}
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-medium text-slate-100">{overlay.displayName}</h3>
                            <span className="text-xs px-2 py-1 bg-slate-700 text-slate-300 rounded">
                              {overlay.category}
                            </span>
                          </div>
                          <p className="text-sm text-slate-400">{overlay.description}</p>
                          {overlay.keywords.length > 0 && (
                            <div className="flex gap-1 mt-1">
                              {overlay.keywords.slice(0, 3).map(keyword => (
                                <span key={keyword} className="text-xs text-slate-500 bg-slate-800 px-1 rounded">
                                  {keyword}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* ENABLE TOGGLE */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (isAvailable) {
                            handleOverlayToggle(overlay.name);
                          }
                        }}
                        disabled={!isAvailable}
                        className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                          isEnabled
                            ? 'bg-green-600 text-white hover:bg-green-700'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600 hover:text-white'
                        } ${!isAvailable ? 'cursor-not-allowed opacity-50' : ''}`}
                      >
                        {isEnabled ? 'Enabled' : 'Enable'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* FOOTER */}
        <div className="p-4 border-t border-slate-700 bg-slate-800 text-sm text-slate-400">
          <div className="flex justify-between items-center">
            <span>
              Showing {filteredOverlays.length} overlay{filteredOverlays.length !== 1 ? 's' : ''} 
              {selectedView !== 'BOTH' && ` for ${selectedView}`}
            </span>
            <div className="flex gap-4 text-xs">
              <span><kbd className="px-1 bg-slate-700 text-slate-300 rounded">Esc</kbd> Close</span>
              <span><kbd className="px-1 bg-slate-700 text-slate-300 rounded">Enter</kbd> Enable Selected</span>
              <span><kbd className="px-1 bg-slate-700 text-slate-300 rounded">Del</kbd> Disable Selected</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
