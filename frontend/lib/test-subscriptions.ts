import { SubscriptionConfig } from './ChartStuff/chart-types'

/**
 * DUMMY TEST DATA FOR MARKET DATA EMITTER
 * 
 * Provides realistic subscription configurations for testing
 * with different update frequencies based on time ranges
 */

// Test subscription configurations with realistic update frequencies
export const TEST_SUBSCRIPTIONS: SubscriptionConfig[] = [
  // 1D subscriptions - update every second (1000ms)
  {
    id: 'yes_1D_AAPL',
    updateFrequency: 1000, // 1 second
    historyLimit: 1000
  },
  {
    id: 'no_1D_AAPL', 
    updateFrequency: 1000, // 1 second
    historyLimit: 1000
  },
  {
    id: 'yes_1D_TSLA',
    updateFrequency: 1000, // 1 second
    historyLimit: 1000
  },
  {
    id: 'no_1D_TSLA',
    updateFrequency: 1000, // 1 second
    historyLimit: 1000
  },

  // 1W subscriptions - update every minute (60000ms)
  {
    id: 'yes_1W_AAPL',
    updateFrequency: 60000, // 1 minute
    historyLimit: 1000
  },
  {
    id: 'no_1W_AAPL',
    updateFrequency: 60000, // 1 minute
    historyLimit: 1000
  },
  {
    id: 'yes_1W_TSLA',
    updateFrequency: 60000, // 1 minute
    historyLimit: 1000
  },
  {
    id: 'no_1W_TSLA',
    updateFrequency: 60000, // 1 minute
    historyLimit: 1000
  },

  // 1M subscriptions - update every hour (3600000ms)
  {
    id: 'yes_1M_AAPL',
    updateFrequency: 3600000, // 1 hour
    historyLimit: 1000
  },
  {
    id: 'no_1M_AAPL',
    updateFrequency: 3600000, // 1 hour
    historyLimit: 1000
  },
  {
    id: 'yes_1M_TSLA',
    updateFrequency: 3600000, // 1 hour
    historyLimit: 1000
  },
  {
    id: 'no_1M_TSLA',
    updateFrequency: 3600000, // 1 hour
    historyLimit: 1000
  },

  // 1Y subscriptions - update every day (86400000ms)
  {
    id: 'yes_1Y_AAPL',
    updateFrequency: 86400000, // 1 day
    historyLimit: 1000
  },
  {
    id: 'no_1Y_AAPL',
    updateFrequency: 86400000, // 1 day
    historyLimit: 1000
  },
  {
    id: 'yes_1Y_TSLA',
    updateFrequency: 86400000, // 1 day
    historyLimit: 1000
  },
  {
    id: 'no_1Y_TSLA',
    updateFrequency: 86400000, // 1 day
    historyLimit: 1000
  }
]

// Helper function to get subscription by pattern
export function getSubscriptionConfig(seriesType: 'yes' | 'no', timeRange: '1H' | '1W' | '1M' | '1Y', symbol: string = 'AAPL'): SubscriptionConfig | undefined {
  const id = `${seriesType}_${timeRange}_${symbol}`
  return TEST_SUBSCRIPTIONS.find(sub => sub.id === id)
}

// Helper function to get all subscriptions for a time range
export function getSubscriptionsForTimeRange(timeRange: '1H' | '1W' | '1M' | '1Y'): SubscriptionConfig[] {
  return TEST_SUBSCRIPTIONS.filter(sub => sub.id.includes(`_${timeRange}_`))
}

// Helper function to get all subscriptions for a series type
export function getSubscriptionsForSeriesType(seriesType: 'yes' | 'no'): SubscriptionConfig[] {
  return TEST_SUBSCRIPTIONS.filter(sub => sub.id.startsWith(`${seriesType}_`))
}

// Quick test data for immediate testing
export const QUICK_TEST_SUBSCRIPTIONS: SubscriptionConfig[] = [
  {
    id: 'test_yes_fast',
    updateFrequency: 500, // 0.5 seconds for quick testing
    historyLimit: 100
  },
  {
    id: 'test_no_fast',
    updateFrequency: 500, // 0.5 seconds for quick testing
    historyLimit: 100
  }
]

/**
 * USAGE EXAMPLES:
 * 
 * // Get specific subscription
 * const config = getSubscriptionConfig('yes', '1H', 'AAPL')
 * 
 * // Get all daily subscriptions
 * const dailySubs = getSubscriptionsForTimeRange('1H')
 * 
 * // Get all YES subscriptions
 * const yesSubs = getSubscriptionsForSeriesType('yes')
 */
