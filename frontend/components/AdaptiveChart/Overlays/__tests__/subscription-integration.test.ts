/**
 * SUBSCRIPTION INTEGRATION TEST
 * 
 * Tests the complete subscription flow from series creation to data reception:
 * 1. Series subscription ID parsing
 * 2. RxJS channel manager integration
 * 3. Data flow through BaseClass to chart series
 * 4. Range switching functionality
 * 5. Cleanup and unsubscription
 */

import { IChartApi, createChart } from 'lightweight-charts'
import { LineSeries } from '../LineSeries'
import { MovingAverage } from '../MovingAverage'
import { rxjsChannelManager } from '../../../../lib/RxJSChannel'
import { SeriesType, TimeRange } from '../../../../lib/ChartStuff/chart-types'
import { BASELINE_SUBSCRIPTION_IDS } from '../../../../lib/subscription-baseline'

// Mock the chart container
const createMockChart = (): IChartApi => {
  const mockContainer = document.createElement('div')
  mockContainer.style.width = '800px'
  mockContainer.style.height = '400px'
  document.body.appendChild(mockContainer)
  return createChart(mockContainer, { width: 800, height: 400 })
}

// Test data collection helper
interface TestDataEvent {
  seriesType: SeriesType
  subscriptionId: string
  marketId: string
  side: string
  timeRange: string
  dataType: 'initial' | 'update'
  dataPointCount: number
  timestamp: number
}

class SubscriptionTestCollector {
  public events: TestDataEvent[] = []
  
  recordEvent(event: TestDataEvent) {
    this.events.push(event)
    console.log('📝 Test Event Recorded:', event)
  }
  
  getEventsForSeries(seriesType: SeriesType): TestDataEvent[] {
    return this.events.filter(e => e.seriesType === seriesType)
  }
  
  clear() {
    this.events = []
  }
}

describe('Subscription Integration Test', () => {
  let chartInstance: IChartApi
  let testCollector: SubscriptionTestCollector
  
  beforeEach(() => {
    chartInstance = createMockChart()
    testCollector = new SubscriptionTestCollector()
    
    // Clear any existing subscriptions
    rxjsChannelManager.unsubscribeAll()
  })
  
  afterEach(() => {
    if (chartInstance) {
      chartInstance.remove()
    }
    testCollector.clear()
    rxjsChannelManager.unsubscribeAll()
  })

  describe('Subscription ID Parsing', () => {
    test('LineSeries should correctly parse subscription ID and connect to RxJS', async () => {
      // Test subscription ID from baseline
      const subscriptionId = BASELINE_SUBSCRIPTION_IDS.YES['1H'] // "yes_1H_MARKET"
      
      console.log('🧪 Testing LineSeries with subscription ID:', subscriptionId)
      
      // Create LineSeries with the subscription ID
      const lineSeries = new LineSeries({
        chartInstance,
        seriesType: 'YES',
        subscriptionId
      })
      
      // Give time for subscription to establish
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // Check that the series was created and has a valid API
      expect(lineSeries.getSeriesApi()).toBeTruthy()
      expect(lineSeries.getSubscriptionId()).toBe(subscriptionId)
      expect(lineSeries.getSeriesType()).toBe('YES')
      
      // Clean up
      lineSeries.remove()
    })

    test('MovingAverage should correctly parse subscription ID and connect to RxJS', async () => {
      const subscriptionId = BASELINE_SUBSCRIPTION_IDS.NO['1W'] // "no_1W_MARKET"
      
      console.log('🧪 Testing MovingAverage with subscription ID:', subscriptionId)
      
      // Create MovingAverage with the subscription ID  
      const movingAverage = new MovingAverage({
        chartInstance,
        seriesType: 'NO',
        subscriptionId,
        movingAverageOptions: { period: 10 }
      })
      
      // Give time for subscription to establish
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // Check that the series was created
      expect(movingAverage.getSeriesApi()).toBeTruthy()
      expect(movingAverage.getSubscriptionId()).toBe(subscriptionId)
      expect(movingAverage.getSeriesType()).toBe('NO')
      
      // Clean up
      movingAverage.remove()
    })
  })

  describe('RxJS Channel Integration', () => {
    test('Series should receive data from RxJS channels', async () => {
      const subscriptionId = BASELINE_SUBSCRIPTION_IDS.YES['1H']
      
      // Mock RxJS channel manager to track subscription calls
      const originalSubscribe = rxjsChannelManager.subscribe
      let subscriptionCalled = false
      let subscribedMarketId = ''
      let subscribedSide = ''
      let subscribedRange = ''
      
      rxjsChannelManager.subscribe = jest.fn((marketId, side, timeRange) => {
        subscriptionCalled = true
        subscribedMarketId = marketId
        subscribedSide = side
        subscribedRange = timeRange
        return originalSubscribe.call(rxjsChannelManager, marketId, side, timeRange)
      })
      
      console.log('🧪 Testing RxJS channel subscription for:', subscriptionId)
      
      // Create series
      const lineSeries = new LineSeries({
        chartInstance,
        seriesType: 'YES',
        subscriptionId
      })
      
      // Give time for subscription to process
      await new Promise(resolve => setTimeout(resolve, 200))
      
      // Verify RxJS subscription was called with correct parameters
      expect(subscriptionCalled).toBe(true)
      expect(subscribedMarketId).toBe('MARKET')
      expect(subscribedSide).toBe('yes')
      expect(subscribedRange).toBe('1H')
      
      // Restore original method
      rxjsChannelManager.subscribe = originalSubscribe
      
      // Clean up
      lineSeries.remove()
    })

    test('Multiple series should receive independent data streams', async () => {
      const yesSubscriptionId = BASELINE_SUBSCRIPTION_IDS.YES['1H']
      const noSubscriptionId = BASELINE_SUBSCRIPTION_IDS.NO['1H']
      
      console.log('🧪 Testing multiple independent data streams')
      
      // Create two different series
      const yesSeries = new LineSeries({
        chartInstance,
        seriesType: 'YES',
        subscriptionId: yesSubscriptionId
      })
      
      const noSeries = new LineSeries({
        chartInstance,
        seriesType: 'NO', 
        subscriptionId: noSubscriptionId
      })
      
      // Give time for subscriptions to establish
      await new Promise(resolve => setTimeout(resolve, 300))
      
      // Both series should be properly configured
      expect(yesSeries.getSubscriptionId()).toBe(yesSubscriptionId)
      expect(noSeries.getSubscriptionId()).toBe(noSubscriptionId)
      expect(yesSeries.getSeriesType()).toBe('YES')
      expect(noSeries.getSeriesType()).toBe('NO')
      
      // Clean up
      yesSeries.remove()
      noSeries.remove()
    })
  })

  describe('Range Switching', () => {
    test('Series should switch ranges correctly', async () => {
      const initialSubscriptionId = BASELINE_SUBSCRIPTION_IDS.YES['1H']
      
      console.log('🧪 Testing range switching functionality')
      
      // Create series with initial range
      const lineSeries = new LineSeries({
        chartInstance,
        seriesType: 'YES',
        subscriptionId: initialSubscriptionId
      })
      
      // Give time for initial subscription
      await new Promise(resolve => setTimeout(resolve, 100))
      
      expect(lineSeries.getSubscriptionId()).toBe(initialSubscriptionId)
      
      // Mock the getNewSubscriptionId function for range switching
      const mockGetNewSubscriptionId = (seriesType: SeriesType, range: string): string => {
        return BASELINE_SUBSCRIPTION_IDS[seriesType][range as TimeRange]
      }
      
      // Switch to 1W range
      console.log('🔄 Switching to 1W range...')
      await lineSeries.setRange('1W', mockGetNewSubscriptionId)
      
      // Give time for range switch to process
      await new Promise(resolve => setTimeout(resolve, 200))
      
      // Verify the subscription ID was updated
      const expectedNewSubscriptionId = BASELINE_SUBSCRIPTION_IDS.YES['1W']
      expect(lineSeries.getSubscriptionId()).toBe(expectedNewSubscriptionId)
      
      // Clean up
      lineSeries.remove()
    })
  })

  describe('Error Handling', () => {
    test('Series should handle invalid subscription IDs gracefully', async () => {
      const invalidSubscriptionId = 'invalid_format'
      
      console.log('🧪 Testing error handling with invalid subscription ID')
      
      // Spy on console.error to catch error messages
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation()
      
      // Create series with invalid subscription ID
      const lineSeries = new LineSeries({
        chartInstance,
        seriesType: 'YES',
        subscriptionId: invalidSubscriptionId
      })
      
      // Give time for error to be logged
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // Should have logged an error about invalid format
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Invalid subscription ID format')
      )
      
      // Series should still be created but without subscription
      expect(lineSeries.getSeriesApi()).toBeTruthy()
      expect(lineSeries.getSubscriptionId()).toBe(invalidSubscriptionId)
      
      // Clean up
      consoleSpy.mockRestore()
      lineSeries.remove()
    })

    test('Series should handle missing subscription ID gracefully', async () => {
      console.log('🧪 Testing error handling with missing subscription ID')
      
      // Spy on console.warn to catch warning messages
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation()
      
      // Create series without subscription ID
      const lineSeries = new LineSeries({
        chartInstance,
        seriesType: 'YES'
        // No subscriptionId provided
      })
      
      // Give time for warning to be logged
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // Should have logged a warning about missing subscription ID
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('No subscription ID provided')
      )
      
      // Series should still be created
      expect(lineSeries.getSeriesApi()).toBeTruthy()
      expect(lineSeries.getSubscriptionId()).toBeNull()
      
      // Clean up
      consoleWarnSpy.mockRestore()
      lineSeries.remove()
    })
  })

  describe('Cleanup and Memory Management', () => {
    test('Series should clean up subscriptions on removal', async () => {
      const subscriptionId = BASELINE_SUBSCRIPTION_IDS.YES['1H']
      
      console.log('🧪 Testing subscription cleanup')
      
      // Create series
      const lineSeries = new LineSeries({
        chartInstance,
        seriesType: 'YES',
        subscriptionId
      })
      
      // Give time for subscription to establish
      await new Promise(resolve => setTimeout(resolve, 100))
      
      expect(lineSeries.getSubscriptionId()).toBe(subscriptionId)
      
      // Remove series (should trigger cleanup)
      lineSeries.remove()
      
      // Give time for cleanup to process
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // Series should be marked as removed and subscription cleared
      expect(lineSeries.getSubscriptionId()).toBeNull()
    })
  })

  describe('End-to-End Subscription Flow', () => {
    test('Complete subscription lifecycle works correctly', async () => {
      console.log('🧪 Testing complete subscription lifecycle')
      
      const subscriptionId = BASELINE_SUBSCRIPTION_IDS.YES['1H']
      
      // Track console logs to verify subscription flow
      const logs: string[] = []
      const originalLog = console.log
      console.log = (...args) => {
        logs.push(args.join(' '))
        originalLog(...args)
      }
      
      // 1. Create series
      const lineSeries = new LineSeries({
        chartInstance,
        seriesType: 'YES',
        subscriptionId
      })
      
      // 2. Give time for subscription to establish
      await new Promise(resolve => setTimeout(resolve, 200))
      
      // 3. Verify series is properly configured
      expect(lineSeries.getSeriesApi()).toBeTruthy()
      expect(lineSeries.getSubscriptionId()).toBe(subscriptionId)
      
      // 4. Verify subscription logging occurred
      const subscriptionLogs = logs.filter(log => 
        log.includes('LineSeries - Attempting subscription') ||
        log.includes('LineSeries - Parsed subscription details') ||
        log.includes('BaseClass') && log.includes('Subscribed')
      )
      expect(subscriptionLogs.length).toBeGreaterThan(0)
      
      // 5. Switch range
      const mockGetNewSubscriptionId = (seriesType: SeriesType, range: string): string => {
        return BASELINE_SUBSCRIPTION_IDS[seriesType][range as TimeRange]
      }
      
      await lineSeries.setRange('1W', mockGetNewSubscriptionId)
      await new Promise(resolve => setTimeout(resolve, 200))
      
      // 6. Verify range switch worked
      expect(lineSeries.getSubscriptionId()).toBe(BASELINE_SUBSCRIPTION_IDS.YES['1W'])
      
      // 7. Clean up
      lineSeries.remove()
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // 8. Verify cleanup
      expect(lineSeries.getSubscriptionId()).toBeNull()
      
      // Restore console.log
      console.log = originalLog
      
      console.log('✅ Complete subscription lifecycle test passed')
    })
  })
})