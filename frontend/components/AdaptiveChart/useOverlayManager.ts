import { useEffect, useRef, useCallback, MutableRefObject } from 'react'
import { IChartApi } from 'lightweight-charts'
import { useOverlayState } from './hooks/useOverlayState'
import { useChartViewState } from './hooks/useChartViewState'
import { useChartRangeState } from './hooks/useChartRangeState'
import SeriesClass from './Overlays/BaseClass'
import { MovingAverage } from './Overlays/MovingAverage'
import { BollingerBands } from './Overlays/BollingerBands'
import { CandleStick } from './Overlays/CandleStick'
import { LineSeries } from './Overlays/LineSeries'
import { Volume } from './Overlays/Volume'
import { SeriesType, TimeRange, Overlay } from '../../lib/ChartStuff/chart-types'
import { OVERLAY_REGISTRY } from '../../lib/ChartStuff/overlay-registry'
import { generateSubscriptionId } from '../../lib/ChartStuff/subscription_baseline'
import { useMarketSubscriptionState } from './hooks/useMarketSubscriptionState'

/**
 * OVERLAY MANAGER HOOK
 * 
 * ARCHITECTURE:
 * This hook acts as the bridge between Redux overlay state and actual BaseClass instances.
 * It listens to Redux changes and manages the lifecycle of chart overlay objects.
 * 
 * KEY RESPONSIBILITIES:
 * 1. Create BaseClass instances when overlays are enabled in Redux
 * 2. Destroy all overlays and recreate when view changes (YES/NO/BOTH)
 * 3. Call setRange() on existing overlays when range changes
 * 4. Handle overlay enable/disable without recreating instances
 * 5. Cleanup all instances on unmount
 * 
 * STATE MANAGEMENT:
 * - Redux Store: Source of truth for overlay configuration
 * - overlayInstances: Map of actual BaseClass instances
 * - Compatible overlays recreated on view change
 * - Range changes update existing instances
 */

// NOT A BASE_CLASS - one of the actual overlays
type ConcreteSeriesClass = new (options: any) => SeriesClass

const OVERLAY_CLASS_MAP: Record<string, ConcreteSeriesClass> = {
  // PRICE SERIES - Core price display (default enabled)
  'yes_price_series': LineSeries,
  'no_price_series': LineSeries,
  'price_series': LineSeries,             // Universal
  // Registry names from OVERLAY_REGISTRY
  'yes_moving_average': MovingAverage,
  'no_moving_average': MovingAverage,
  'moving_average': MovingAverage,        // Universal
  'yes_bollinger_bands': BollingerBands,   // TODO: Replace with BollingerBands when implemented
  'no_bollinger_bands': BollingerBands,    // TODO: Replace with BollingerBands when implemented
  'bollinger_bands': MovingAverage,       // Universal
  'yes_rsi': MovingAverage,               // TODO: Replace with RSI when implemented
  'no_rsi': MovingAverage,                // TODO: Replace with RSI when implemented
  'rsi': MovingAverage,                   // Universal
  'universal_volume_profile': Volume,    // TODO: Replace with VolumeProfile when implemented
  'yes_support_resistance': MovingAverage, // TODO: Replace with SupportResistance when implemented
  'no_support_resistance': MovingAverage,  // TODO: Replace with SupportResistance when implemented
  'support_resistance': MovingAverage,     // Universal
  // CANDLESTICK OVERLAYS
  'yes_candlestick': CandleStick,
  'no_candlestick': CandleStick,
  'candlestick': CandleStick,             // Universal
}

interface UseOverlayManagerProps {
  chartInstanceRef: MutableRefObject<IChartApi | null>
  chartId: string
  marketId: string  // Add marketId prop
  platform?: string  // Add platform for context
}
const BOTTOM_CLASS_MAP: string[] = [
  'yes_volume_profile',
  'no_volume_profile',
  'universal_volume_profile'
]

export function useOverlayManager({ chartInstanceRef, chartId, marketId, platform }: UseOverlayManagerProps) {
  // TRACE: Log useOverlayManager reception - now showing what it receives
  
  // Redux state hooks - now using chartId for isolated state
  const { overlays, addOverlay } = useOverlayState(chartId)
  const { selectedView } = useChartViewState(chartId)
  const { selectedRange } = useChartRangeState(chartId)
  const { getSubscriptionId } = useMarketSubscriptionState(chartId) // Get subscription IDs
  
  // Map to store actual SeriesClass instances
  // Memoize this in later iterations, make lookups more efficient
  const overlayInstancesRef = useRef<Map<string, SeriesClass>>(new Map())

  /* @variable universal market id
  *	 follows format marketId&side&range - where market id is in th
  */

  if (!platform) {
    console.warn('No platform provided. Defaulting to "default".');
    platform = 'kalshi';
  }

  /*
  * IMPORTANT - represents our marketId prefix in our channel subscription key
  */
  let universal_market_id: string | null = `${platform}_${marketId}`

  // Track previous state to detect changes
  const previousStateRef = useRef({
    view: selectedView,
    range: selectedRange,
    overlayKeys: new Set<string>()
  })

  /**
   * HELPER: Get overlay class constructor by name
   */
  const getOverlayClass = useCallback((overlayName: string): ConcreteSeriesClass | null => {
    return OVERLAY_CLASS_MAP[overlayName] || null
  }, [])

  /**
   * CORE: Create SeriesClass instance for overlay
   */

  const createOverlayInstance = useCallback((overlayKey: string, overlay: Overlay): SeriesClass | null => {
    const chartInstance = chartInstanceRef.current
    if (!chartInstance) {
      return null
    }

    // Use overlay key directly as overlay name (no range suffix to remove)
    const overlayName = overlayKey

    //where do you define the overlay class 
    const OverlayClass = getOverlayClass(overlayName)
    
    if (!OverlayClass) {
      return null
    }

    //build the overlay with the actual parent 
    try {
      // FIXED: Use real marketId with platform prefix if available, otherwise fall back to Redux/baseline
      const reduxSubscriptionId = getSubscriptionId(overlay.type, overlay.range)
      
      // Generate subscription ID with platform prefix to match WebSocket emission format
      // @TODO: merge this into a singleton repo
      let realMarketSubscriptionId = null
      if (marketId && platform) {
        const platformPrefixedMarketId = `${platform.toLowerCase()}_${marketId}`

        //The range of the overlay should be controlled by the global state - but the view is not neccessarily controlled
        // by the global state because of the both view - each series maintains it's yes/no view 
        realMarketSubscriptionId = generateSubscriptionId(overlay.type, selectedRange, platformPrefixedMarketId)
      } 
      
      // Priority: real marketId (with platform). No fallbacks
      const subscriptionId = realMarketSubscriptionId
	    universal_market_id = realMarketSubscriptionId
      
      // TRACE: Log subscription ID generation logic with enhanced details
      
      
      const instance = new OverlayClass({
        chartInstance,
        seriesType: overlay.type,
        subscriptionId
      })
      
      
      return instance
    } catch (error) {
      return null
    }
  }, [getOverlayClass, getSubscriptionId])

  /**
   * HELPER: Destroy overlay instance and cleanup
   */
  const destroyOverlayInstance = useCallback((overlayKey: string) => {
    const instance = overlayInstancesRef.current.get(overlayKey)
    if (instance) {
      try {
        instance.remove()
        overlayInstancesRef.current.delete(overlayKey)
      } catch (error) {
        // Error destroying overlay
      }
    }
  }, [])

  /**
   * HELPER: Check if overlay is compatible with current view
   */
  const isOverlayCompatible = useCallback((overlay: Overlay): boolean => {
    if (selectedView === 'BOTH') return true
    return overlay.type === selectedView
  }, [selectedView])

  /**
   * HELPER: Ensure default price series overlays are enabled
   * Price series should always be available as the core chart display
   */
  const ensureDefaultPriceSeriesEnabled = useCallback(() => {
    // Helper to create price series overlay key
    const getPriceSeriesKey = (seriesType: SeriesType, range: TimeRange) => 
      `${seriesType.toLowerCase()}_price_series`
    
    // Auto-enable price series based on current view
    if (selectedView === 'BOTH') {
      // Enable both YES and NO price series
      const yesKey = getPriceSeriesKey('YES', selectedRange)
      const noKey = getPriceSeriesKey('NO', selectedRange)
      
      if (!overlays[yesKey]) {
        addOverlay(yesKey, {
          type: 'YES',
          range: selectedRange,
          enabled: true,
          available: true
        })
      }
      
      if (!overlays[noKey]) {
        addOverlay(noKey, {
          type: 'NO', 
          range: selectedRange,
          enabled: true,
          available: true
        })
      }
    } else {
      // Enable price series for single view (YES or NO)
      const priceKey = getPriceSeriesKey(selectedView, selectedRange)
      
      if (!overlays[priceKey]) {
        addOverlay(priceKey, {
          type: selectedView,
          range: selectedRange,
          enabled: true,
          available: true
        })
      }
    }
  }, [selectedView, selectedRange, overlays, addOverlay])

  /**
   * EFFECT: Handle view changes (destroy all, recreate compatible)
   */
  useEffect(() => {
    const previousView = previousStateRef.current.view
    
    if (previousView !== selectedView) {
      
      // Step 1: Destroy ALL existing overlay instances
      const currentInstances = Array.from(overlayInstancesRef.current.keys())
      currentInstances.forEach(overlayKey => {
        destroyOverlayInstance(overlayKey)
      })
      
      // Step 2: Recreate only compatible overlays
      Object.entries(overlays).forEach(([overlayKey, overlay]) => {
        if (overlay.enabled && isOverlayCompatible(overlay)) {
          const instance = createOverlayInstance(overlayKey, overlay)
          if (instance) {
            overlayInstancesRef.current.set(overlayKey, instance)
          }
        }
      })
      
      // Update previous state
      previousStateRef.current.view = selectedView
      
    }
  }, [selectedView, overlays, destroyOverlayInstance, createOverlayInstance, isOverlayCompatible])

  /**
   * EFFECT: Handle range changes (call setRange on existing instances)
   * 
   */
  useEffect(() => {
    const previousRange = previousStateRef.current.range
    
    if (previousRange !== selectedRange) {
      
      // Call setRange() on all existing instances
      overlayInstancesRef.current.forEach((instance, overlayKey) => {
        try {
          // Function to get new subscription ID for a given series type and range
          instance.setRange(selectedRange, marketId)
        } catch (error) {
          // Error updating range
        }
      })
      
      // Update previous state
      previousStateRef.current.range = selectedRange
      
    }
  }, [selectedRange])

  /**
   * EFFECT 1: Handle overlay additions (when new overlays are added to Redux)
   */
  useEffect(() => {
    const currentOverlayKeys = new Set(Object.keys(overlays))
    const previousOverlayKeys = previousStateRef.current.overlayKeys
    const addedKeys = Array.from(currentOverlayKeys).filter(key => !previousOverlayKeys.has(key))
    
    if (addedKeys.length > 0) {
      
      addedKeys.forEach(overlayKey => {
        const overlay = overlays[overlayKey]
        if (overlay.enabled && isOverlayCompatible(overlay)) {
          const instance = createOverlayInstance(overlayKey, overlay)
          if (instance) {
            overlayInstancesRef.current.set(overlayKey, instance)
            if (overlayKey in BOTTOM_CLASS_MAP) {
              setWindowSize()
            }
          }
        } else {
          // Skipping overlay (disabled or incompatible)
        }
      })
      
      // Update previous overlay keys to include new ones
      previousStateRef.current.overlayKeys = currentOverlayKeys
    }
  }, [Object.keys(overlays).join(','), createOverlayInstance, isOverlayCompatible])

  /**
   * EFFECT 2: Handle overlay removals (when overlays are removed from Redux)
   */
  useEffect(() => {
    const currentOverlayKeys = new Set(Object.keys(overlays))
    const previousOverlayKeys = previousStateRef.current.overlayKeys
    const removedKeys = Array.from(previousOverlayKeys).filter(key => !currentOverlayKeys.has(key))
    
    if (removedKeys.length > 0) {
      
      removedKeys.forEach(overlayKey => {
        //check if removed was the universal profile
        if (overlayKey in BOTTOM_CLASS_MAP) {
              resetWindowSize()
        }
        destroyOverlayInstance(overlayKey)
      })
      
      // Update previous overlay keys to remove deleted ones
      previousStateRef.current.overlayKeys = currentOverlayKeys
    }
  }, [Object.keys(overlays).join(','), destroyOverlayInstance])

  /**
   * EFFECT 3: Handle overlay enable/disable state changes (when existing overlays are toggled)
   */
  useEffect(() => {
    const overlayStatesString = JSON.stringify(Object.fromEntries(
      Object.entries(overlays).map(([key, overlay]) => [key, { enabled: overlay.enabled, available: overlay.available }])
    ))
    
    
    Object.entries(overlays).forEach(([overlayKey, overlay]) => {
      //check if removed was the universal profile
        
      const hasInstance = overlayInstancesRef.current.has(overlayKey)
      const shouldHaveInstance = overlay.enabled && isOverlayCompatible(overlay)
      
      if (hasInstance && !shouldHaveInstance) {
        if (overlayKey in BOTTOM_CLASS_MAP) {
              resetWindowSize()
        }
        destroyOverlayInstance(overlayKey)
      } else if (!hasInstance && shouldHaveInstance) {
        const instance = createOverlayInstance(overlayKey, overlay)
        if (overlayKey in BOTTOM_CLASS_MAP) {
              setWindowSize()
        }
        if (instance) {
          overlayInstancesRef.current.set(overlayKey, instance)
        }
      }
    })
  }, [
    JSON.stringify(Object.fromEntries(
      Object.entries(overlays).map(([key, overlay]) => [key, { enabled: overlay.enabled, available: overlay.available }])
    )),
    destroyOverlayInstance, 
    createOverlayInstance, 
    isOverlayCompatible
  ])


  /**
   * EFFECT: Ensure default price series overlays are enabled
   * This runs whenever view or range changes to auto-enable price series
   */
  useEffect(() => {
    ensureDefaultPriceSeriesEnabled()
  }, [selectedView, selectedRange, ensureDefaultPriceSeriesEnabled])

  /**
   * CLEANUP: Destroy all instances on unmount
   */
  useEffect(() => {
    return () => {
      console.log('🧹 OverlayManager - Cleaning up all overlay instances on unmount')
      const currentInstances = Array.from(overlayInstancesRef.current.keys())
      currentInstances.forEach(overlayKey => {
        destroyOverlayInstance(overlayKey)
      })
    }
  }, [destroyOverlayInstance])

  /**
   * PUBLIC API: Get current overlay instances (for debugging)
   */
  const getActiveOverlays = useCallback(() => {
    return Array.from(overlayInstancesRef.current.entries()).map(([key, instance]) => ({
      key,
      className: instance.constructor.name,
      seriesType: instance.getSeriesType()
    }))
  }, [])

  const getOverlayInstance = useCallback((overlayKey: string): SeriesClass | null => {
    return overlayInstancesRef.current.get(overlayKey) || null
  }, [])


  const setWindowSize = useCallback(() => {
    
    // Iterate through every overlay instance that is not in the BOTTOM_CLASS_MAP
    overlayInstancesRef.current.forEach((instance, overlayKey) => {
      // Check if this overlay is NOT in the bottom class map
      if (!BOTTOM_CLASS_MAP.includes(overlayKey)) {
        try {
          const seriesApi = instance.getSeriesApi()
          if (seriesApi) {
            // Apply scale margins to push this series away from bottom (where volume will be)
            seriesApi.priceScale().applyOptions({
              scaleMargins: {
                top: 0.1,    // 10% away from the top
                bottom: 0.4, // 40% away from the bottom (leaving space for volume)
              }
            })
          } else {
            // No series API found
          }
        } catch (error) {
          // Error setting scale margins
        }
      } else {
        // Skipping bottom overlay
      }
    })
  }, [])

  /*
   * Settor and Gettor for universal market id based on side, range
   *
   * @TODO - merge this into the utilites
   * */
  function createNewSubscription(newRange: TimeRange, newView: SeriesType): string | null {
    if (!universal_market_id) {
      console.error("No subscription detected and react state change detected. Aborting range change to avoid runtime error.")
      return null
    }

    let new_subscription = [universal_market_id, newView, newRange].join('&')
    console.log("New universal market id", new_subscription)

    return new_subscription
  }

  /*
  * Resets window size to original for all non bottom_class_map series 
  * If some other overlay is removed, we reset to default margins
  */
  const resetWindowSize = useCallback(() => {
    
    // Iterate through every overlay instance that is not in the BOTTOM_CLASS_MAP
    overlayInstancesRef.current.forEach((instance, overlayKey) => {
      // Check if this overlay is NOT in the bottom class map
      if (!BOTTOM_CLASS_MAP.includes(overlayKey)) {
        try {
          const seriesApi = instance.getSeriesApi()
          if (seriesApi) {
            // Reset to default scale margins (no restrictions)
            seriesApi.priceScale().applyOptions({
              scaleMargins: {
                top: 0.1,    // Standard top margin
                bottom: 0.1, // Standard bottom margin (full space available)
              }
            })
          } else {
            // No series API found
          }
        } catch (error) {
          // Error resetting scale margins
        }
      } else {
        // Skipping bottom overlay
      }
    })
  }, [])



  return {
    getActiveOverlays,
    getOverlayInstance,
    activeOverlayCount: overlayInstancesRef.current.size
  }
  
}
