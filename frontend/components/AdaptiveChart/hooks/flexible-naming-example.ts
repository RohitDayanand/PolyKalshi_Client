// ALTERNATIVE: More Flexible Naming System

// 1. Direct mapping without suffix assumptions
const FLEXIBLE_OVERLAY_CLASS_MAP: Record<string, ConcreteSeriesClass> = {
  'my_awesome_bull_trend_1D': TrendFollower,
  'my_awesome_bear_trend_1D': TrendFollower,
  'profit_predictor_daily': MomentumOscillator,
  'magic_volatility_weekly': VolatilityBands,
  // Any naming pattern you want!
}

// 2. Modified OverlayManager logic
const createOverlayInstance = useCallback((overlayKey: string, overlay: Overlay): SeriesClass | null => {
  // Option A: Direct lookup (no name extraction)
  const OverlayClass = FLEXIBLE_OVERLAY_CLASS_MAP[overlayKey]
  
  // Option B: Custom parsing logic
  const parts = overlayKey.split('_')
  const baseName = parts.slice(0, -1).join('_') // Everything except last part
  const OverlayClass = OVERLAY_CLASS_MAP[baseName]
  
  // Option C: Regex-based extraction
  const match = overlayKey.match(/^(.+)_(\w+)$/)
  const baseName = match?.[1]
  const OverlayClass = OVERLAY_CLASS_MAP[baseName]
  
  if (!OverlayClass) {
    console.warn(`No class found for overlay: ${overlayKey}`)
    return null
  }
  
  return new OverlayClass({
    chartInstance,
    seriesType: overlay.type,
    subscriptionId: `market_${overlay.type.toLowerCase()}_${overlay.range}`
  })
}, [chartInstance])

// 3. Redux state can use any keys
const flexibleOverlayState = {
  overlays: {
    "my_awesome_bull_trend_1D": { type: "YES", range: "1H", enabled: true },
    "profit_predictor_daily": { type: "YES", range: "1H", enabled: false },
    "magic_volatility_weekly": { type: "NO", range: "1W", enabled: true },
  }
}
