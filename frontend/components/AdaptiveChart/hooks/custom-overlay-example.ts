// EXAMPLE: Custom Overlay Naming Convention

// 1. Custom Overlay Classes
export class TrendFollower extends SeriesClass {
  // Moving average logic but named differently
}

export class VolatilityBands extends SeriesClass {
  // Bollinger bands logic but named differently  
}

export class MomentumOscillator extends SeriesClass {
  // RSI logic but named differently
}

// 2. Custom Registry Names
export const CUSTOM_OVERLAY_REGISTRY = {
  'trend_follower_bulls': {
    name: 'Bull Trend Follower',
    description: 'Tracks upward price momentum',
    category: 'Trend',
    seriesType: 'YES' as SeriesType,
    // ...
  },
  'trend_follower_bears': {
    name: 'Bear Trend Follower', 
    description: 'Tracks downward price momentum',
    category: 'Trend',
    seriesType: 'NO' as SeriesType,
    // ...
  },
  'volatility_bands_bulls': {
    name: 'Bull Volatility Bands',
    description: 'Price volatility envelope for bulls',
    category: 'Volatility',
    seriesType: 'YES' as SeriesType,
    // ...
  },
  'volatility_bands_bears': {
    name: 'Bear Volatility Bands',
    description: 'Price volatility envelope for bears', 
    category: 'Volatility',
    seriesType: 'NO' as SeriesType,
    // ...
  }
}

// 3. Custom Class Mapping
const CUSTOM_OVERLAY_CLASS_MAP: Record<string, ConcreteSeriesClass> = {
  'trend_follower_bulls': TrendFollower,
  'trend_follower_bears': TrendFollower,
  'volatility_bands_bulls': VolatilityBands,
  'volatility_bands_bears': VolatilityBands,
  'momentum_oscillator_bulls': MomentumOscillator,
  'momentum_oscillator_bears': MomentumOscillator,
}

// 4. Redux State Would Look Like:
const customOverlayState = {
  overlays: {
    "trend_follower_bulls_1D": { type: "YES", range: "1H", enabled: true },
    "trend_follower_bears_1D": { type: "NO", range: "1H", enabled: false },
    "volatility_bands_bulls_1W": { type: "YES", range: "1W", enabled: true },
    // etc...
  }
}

// 5. OverlayManager Logic Stays the Same:
const overlayName = overlayKey.replace(`_${overlay.range}`, '')
// "trend_follower_bulls_1D" → "trend_follower_bulls"

const OverlayClass = getOverlayClass(overlayName)
// Returns TrendFollower constructor

const instance = new OverlayClass({
  chartInstance,
  seriesType: overlay.type, // "YES" or "NO"
  subscriptionId: `market_${overlay.type.toLowerCase()}_${overlay.range}`
})
