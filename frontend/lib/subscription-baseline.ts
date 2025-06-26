/**
 * SUBSCRIPTION BASELINE CONFIGURATION
 * 
 * Comprehensive subscription ID mapping for all time ranges and series types.
 * This provides consistent subscription IDs across the entire application.
 */

import { TimeRange, SeriesType } from './ChartStuff/chart-types'

// Base symbols for different markets
export const MARKET_SYMBOLS = {
  DEFAULT: 'MARKET',
  STOCK: 'AAPL',
  CRYPTO: 'BTC',
  FOREX: 'EURUSD',
} as const

// Update frequency mapping per time range (in milliseconds)
export const RANGE_UPDATE_FREQUENCIES = {
  '1H': 1000,    // 1 second - high frequency for day trading
  '1W': 5000,    // 5 seconds - medium frequency for weekly
  '1M': 30000,   // 30 seconds - lower frequency for monthly
  '1Y': 300000,  // 5 minutes - lowest frequency for yearly
} as const

// Cache size mapping per time range
export const RANGE_CACHE_SIZES = {
  '1H': 1440,    // 24 hours * 60 minutes = 1440 points (1 per minute)
  '1W': 672,     // 7 days * 24 hours * 4 = 672 points (1 per 15 minutes)
  '1M': 720,     // 30 days * 24 = 720 points (1 per hour)
  '1Y': 365,     // 365 days = 365 points (1 per day)
} as const

/**
 * Generate subscription ID for a specific series type, range, and symbol
 * Format: marketId&side&range to match RxJS channel key format
 */
export function generateSubscriptionId(
  seriesType: SeriesType,
  range: TimeRange,
  symbol: string = MARKET_SYMBOLS.DEFAULT
): string {
  // Convert SeriesType to lowercase side to match RxJS format
  const side = seriesType.toLowerCase() // 'YES' -> 'yes', 'NO' -> 'no'
  // Use marketId&side&range format to match RxJSChannelManager.generateChannelKey()
  return `${symbol}&${side}&${range}`
}

/**
 * BASELINE SUBSCRIPTION IDS
 * All possible combinations for the default market
 */
export const BASELINE_SUBSCRIPTION_IDS = {
  YES: {
    '1H': generateSubscriptionId('YES', '1H'),
    '1W': generateSubscriptionId('YES', '1W'),
    '1M': generateSubscriptionId('YES', '1M'),
    '1Y': generateSubscriptionId('YES', '1Y'),
  },
  NO: {
    '1H': generateSubscriptionId('NO', '1H'),
    '1W': generateSubscriptionId('NO', '1W'),
    '1M': generateSubscriptionId('NO', '1M'),
    '1Y': generateSubscriptionId('NO', '1Y'),
  }
} as const

/**
 * Generate all subscription configurations for baseline setup
 */
export function generateBaselineSubscriptionConfigs() {
  const configs = []
  
  const ranges: TimeRange[] = ['1H', '1W', '1M', '1Y']
  const types: SeriesType[] = ['YES', 'NO']
  
  for (const range of ranges) {
    for (const type of types) {
      configs.push({
        id: generateSubscriptionId(type, range),
        updateFrequency: RANGE_UPDATE_FREQUENCIES[range],
        historyLimit: RANGE_CACHE_SIZES[range],
        seriesType: type,
        range: range,
        symbol: MARKET_SYMBOLS.DEFAULT
      })
    }
  }
  
  return configs
}

/**
 * Get subscription config for specific series type and range
 */
export function getSubscriptionConfig(seriesType: SeriesType, range: TimeRange) {
  return {
    id: generateSubscriptionId(seriesType, range),
    updateFrequency: RANGE_UPDATE_FREQUENCIES[range],
    historyLimit: RANGE_CACHE_SIZES[range],
    seriesType,
    range,
    symbol: MARKET_SYMBOLS.DEFAULT
  }
}

/**
 * COMPREHENSIVE SUBSCRIPTION REGISTRY
 * All subscription IDs that should be available
 */
export const SUBSCRIPTION_REGISTRY = {
  // Default market subscriptions
  ...BASELINE_SUBSCRIPTION_IDS,
  
  // Stock market subscriptions (AAPL)
  STOCK: {
    YES: {
      '1H': generateSubscriptionId('YES', '1H', MARKET_SYMBOLS.STOCK),
      '1W': generateSubscriptionId('YES', '1W', MARKET_SYMBOLS.STOCK),
      '1M': generateSubscriptionId('YES', '1M', MARKET_SYMBOLS.STOCK),
      '1Y': generateSubscriptionId('YES', '1Y', MARKET_SYMBOLS.STOCK),
    },
    NO: {
      '1H': generateSubscriptionId('NO', '1H', MARKET_SYMBOLS.STOCK),
      '1W': generateSubscriptionId('NO', '1W', MARKET_SYMBOLS.STOCK),
      '1M': generateSubscriptionId('NO', '1M', MARKET_SYMBOLS.STOCK),
      '1Y': generateSubscriptionId('NO', '1Y', MARKET_SYMBOLS.STOCK),
    }
  },
  
  // Crypto market subscriptions (BTC)
  CRYPTO: {
    YES: {
      '1H': generateSubscriptionId('YES', '1H', MARKET_SYMBOLS.CRYPTO),
      '1W': generateSubscriptionId('YES', '1W', MARKET_SYMBOLS.CRYPTO),
      '1M': generateSubscriptionId('YES', '1M', MARKET_SYMBOLS.CRYPTO),
      '1Y': generateSubscriptionId('YES', '1Y', MARKET_SYMBOLS.CRYPTO),
    },
    NO: {
      '1H': generateSubscriptionId('NO', '1H', MARKET_SYMBOLS.CRYPTO),
      '1W': generateSubscriptionId('NO', '1W', MARKET_SYMBOLS.CRYPTO),
      '1M': generateSubscriptionId('NO', '1M', MARKET_SYMBOLS.CRYPTO),
      '1Y': generateSubscriptionId('NO', '1Y', MARKET_SYMBOLS.CRYPTO),
    }
  }
} as const

// Export flattened list of all subscription IDs for easy iteration
export const ALL_SUBSCRIPTION_IDS = Object.values(BASELINE_SUBSCRIPTION_IDS)
  .flatMap(typeIds => Object.values(typeIds))

console.log('📋 Subscription Baseline - Generated IDs:', ALL_SUBSCRIPTION_IDS)
