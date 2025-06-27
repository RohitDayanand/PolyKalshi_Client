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
  marketId: String
): string {
  // Convert SeriesType to lowercase side to match RxJS format
  const side = seriesType.toLowerCase() // 'YES' -> 'yes', 'NO' -> 'no'
  // Use marketId&side&range format to match RxJSChannelManager.generateChannelKey()
  return `${marketId}&${side}&${range}`
}
