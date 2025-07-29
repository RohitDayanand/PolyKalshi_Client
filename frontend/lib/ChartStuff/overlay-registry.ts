import { SeriesType, TimeRange } from './chart-types'

/**
 * OVERLAY REGISTRY
 * 
 * Central registry of all available overlay types with search metadata.
 * Each overlay can be compatible with specific series types (YES, NO, or both).
 */

// OVERLAY METADATA: Defines all available overlay types with search metadata
export interface OverlayMetadata {
  name: string;
  displayName: string;
  description: string;
  category: 'Technical Indicators' | 'Moving Averages' | 'Volatility' | 'Trend Analysis';
  keywords: string[]; // For fuzzy search matching
  compatibleWith: SeriesType[]; // Which series types support this overlay
  requiresTimeframe?: TimeRange[]; // Some overlays may need minimum timeframes
}

// OVERLAY REGISTRY: Central registry of all available overlays
export const OVERLAY_REGISTRY: OverlayMetadata[] = [
  // PRICE SERIES - Core price display (always enabled by default)
  {
    name: 'yes_price_series',
    displayName: 'YES Price Line',
    description: 'Main price line for YES market data',
    category: 'Technical Indicators',
    keywords: ['price', 'line', 'chart', 'yes', 'core', 'main'],
    compatibleWith: ['YES'],
  },
  {
    name: 'no_price_series',
    displayName: 'NO Price Line', 
    description: 'Main price line for NO market data',
    category: 'Technical Indicators',
    keywords: ['price', 'line', 'chart', 'no', 'core', 'main'],
    compatibleWith: ['NO'],
  },

  // MOVING AVERAGES - YES specific
  {
    name: 'yes_moving_average',
    displayName: 'YES Moving Average',
    description: '20-period simple moving average for YES markets',
    category: 'Moving Averages',
    keywords: ['ma', 'sma', 'average', 'smooth', 'trend', 'yes', 'bull'],
    compatibleWith: ['YES'],
  },
  // MOVING AVERAGES - NO specific
  {
    name: 'no_moving_average',
    displayName: 'NO Moving Average',
    description: '20-period simple moving average for NO markets',
    category: 'Moving Averages',
    keywords: ['ma', 'sma', 'average', 'smooth', 'trend', 'no', 'bear'],
    compatibleWith: ['NO'],
  },
  // MOVING AVERAGES - Universal (both YES and NO)

  // BOLLINGER BANDS - YES specific
  {
    name: 'yes_bollinger_bands',
    displayName: 'YES Bollinger Bands',
    description: 'Volatility bands around moving average for YES markets',
    category: 'Volatility',
    keywords: ['bb', 'bands', 'volatility', 'bollinger', 'envelope', 'yes', 'bull'],
    compatibleWith: ['YES'],
  },
  // BOLLINGER BANDS - NO specific
  {
    name: 'no_bollinger_bands',
    displayName: 'NO Bollinger Bands',
    description: 'Volatility bands around moving average for NO markets',
    category: 'Volatility',
    keywords: ['bb', 'bands', 'volatility', 'bollinger', 'envelope', 'no', 'bear'],
    compatibleWith: ['NO'],
  },
  // RSI overlays have been commented out to avoid compilation errors.
  // {
  //   name: 'yes_rsi',
  //   displayName: 'YES RSI',
  //   description: 'Relative Strength Index momentum oscillator for YES markets',
  //   category: 'Technical Indicators',
  //   keywords: ['rsi', 'momentum', 'oscillator', 'strength', 'relative', 'yes', 'bull'],
  //   compatibleWith: ['YES'],
  //   requiresTimeframe: ['1W', '1M', '1Y'], // RSI needs longer periods
  // },
  // {
  //   name: 'no_rsi',
  //   displayName: 'NO RSI',
  //   description: 'Relative Strength Index momentum oscillator for NO markets',
  //   category: 'Technical Indicators',
  //   keywords: ['rsi', 'momentum', 'oscillator', 'strength', 'relative', 'no', 'bear'],
  //   compatibleWith: ['NO'],
  //   requiresTimeframe: ['1W', '1M', '1Y'], // RSI needs longer periods
  // },
  // {
  //   name: 'rsi',
  //   displayName: 'Universal RSI',
  //   description: 'Relative Strength Index momentum oscillator for all markets',
  //   category: 'Technical Indicators',
  //   keywords: ['rsi', 'momentum', 'oscillator', 'strength', 'relative', 'universal'],
  //   compatibleWith: ['YES', 'NO'],
  //   requiresTimeframe: ['1W', '1M', '1Y'], // RSI needs longer periods
  // },

  // CANDLESTICK CHARTS - YES specific
  {
    name: 'yes_candlestick',
    displayName: 'YES Candlesticks',
    description: 'OHLC candlestick chart for YES market price action',
    category: 'Technical Indicators',
    keywords: ['candle', 'candlestick', 'ohlc', 'price', 'action', 'yes', 'bull'],
    compatibleWith: ['YES'],
  },
  // CANDLESTICK CHARTS - NO specific
  {
    name: 'no_candlestick',
    displayName: 'NO Candlesticks',
    description: 'OHLC candlestick chart for NO market price action',
    category: 'Technical Indicators',
    keywords: ['candle', 'candlestick', 'ohlc', 'price', 'action', 'no', 'bear'],
    compatibleWith: ['NO'],
  },

  // VOLUME PROFILE - YES specific
  {
    name: 'yes_volume_profile',
    displayName: 'Market Volume Profile',
    description: 'Trading volume at price levels for binary markets',
    category: 'Technical Indicators',
    keywords: ['volume', 'profile', 'poc', 'vwap', 'distribution', 'yes', 'bull'],
    compatibleWith: ['YES'],
  },
  {
    name: 'no_volume_profile',
    displayName: 'Market Volume Profile',
    description: 'Trading volume at price levels for binary markets',
    category: 'Technical Indicators',
    keywords: ['volume', 'profile', 'poc', 'vwap', 'distribution', 'yes', 'bull'],
    compatibleWith: ['NO'],
  },
  // VOLUME PROFILE - NO specific

  // SUPPORT & RESISTANCE - Universal
];

/**
 * HELPER FUNCTIONS for working with the overlay registry
 */

// Get overlay by name
export function getOverlayByName(name: string): OverlayMetadata | undefined {
  return OVERLAY_REGISTRY.find(overlay => overlay.name === name);
}

// Get overlays by category
export function getOverlaysByCategory(category: OverlayMetadata['category']): OverlayMetadata[] {
  return OVERLAY_REGISTRY.filter(overlay => overlay.category === category);
}

// Get overlays compatible with a specific series type
export function getOverlaysForSeriesType(seriesType: SeriesType): OverlayMetadata[] {
  return OVERLAY_REGISTRY.filter(overlay => overlay.compatibleWith.includes(seriesType));
}

// Get overlays that work with a specific timeframe
export function getOverlaysForTimeframe(timeframe: TimeRange): OverlayMetadata[] {
  return OVERLAY_REGISTRY.filter(overlay => 
    !overlay.requiresTimeframe || overlay.requiresTimeframe.includes(timeframe)
  );
}

// Search overlays by keywords
export function searchOverlays(query: string): OverlayMetadata[] {
  if (!query) return OVERLAY_REGISTRY;
  
  const searchLower = query.toLowerCase();
  
  return OVERLAY_REGISTRY.filter(overlay => {
    // Search in display name
    if (overlay.displayName.toLowerCase().includes(searchLower)) return true;
    
    // Search in description
    if (overlay.description.toLowerCase().includes(searchLower)) return true;
    
    // Search in keywords
    return overlay.keywords.some(keyword => 
      keyword.toLowerCase().includes(searchLower)
    );
  });
}

// Get overlay statistics
export function getOverlayStats() {
  const totalOverlays = OVERLAY_REGISTRY.length;
  const yesOnlyOverlays = OVERLAY_REGISTRY.filter(o => 
    o.compatibleWith.length === 1 && o.compatibleWith.includes('YES')
  ).length;
  const noOnlyOverlays = OVERLAY_REGISTRY.filter(o => 
    o.compatibleWith.length === 1 && o.compatibleWith.includes('NO')
  ).length;
  const universalOverlays = OVERLAY_REGISTRY.filter(o => 
    o.compatibleWith.includes('YES') && o.compatibleWith.includes('NO')
  ).length;
  
  const categoryCounts = OVERLAY_REGISTRY.reduce((acc, overlay) => {
    acc[overlay.category] = (acc[overlay.category] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  return {
    totalOverlays,
    yesOnlyOverlays,
    noOnlyOverlays,
    universalOverlays,
    categoryCounts
  };
}
