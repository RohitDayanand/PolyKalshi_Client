/**
 * SUBSCRIPTION INTEGRATION TEST RUNNER
 * 
 * Simple runner to manually execute and validate the subscription integration test
 * This can be run directly with ts-node for quick verification
 */

import { IChartApi, createChart } from 'lightweight-charts'
import { LineSeries } from '../LineSeries'
import { MovingAverage } from '../MovingAverage'
import { BASELINE_SUBSCRIPTION_IDS } from '../../../../lib/subscription-baseline'
import { rxjsChannelManager } from '../../../../lib/RxJSChannelManager'

// Create DOM environment for tests
if (typeof document === 'undefined') {
  const { JSDOM } = require('jsdom')
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>')
  global.document = dom.window.document
  global.window = dom.window as any
}

class SubscriptionTestRunner {
  private chartInstance: IChartApi | null = null
  
  async runTests() {
    console.log('🧪 Starting Subscription Integration Tests...\n')
    
    try {
      await this.setupChart()
      await this.testBasicSubscription()
      await this.testSubscriptionParsing()
      await this.testRangeSwitch()
      await this.testMultipleSeries()
      await this.testErrorHandling()
      
      console.log('\n✅ All subscription integration tests passed!')
      
    } catch (error) {
      console.error('\n❌ Test failed:', error)
      throw error
    } finally {
      this.cleanup()
    }
  }
  
  private async setupChart() {
    console.log('📊 Setting up chart instance...')
    
    const container = document.createElement('div')
    container.style.width = '800px'
    container.style.height = '400px'
    document.body.appendChild(container)
    
    this.chartInstance = createChart(container, {
      width: 800,
      height: 400
    })
    
    console.log('✅ Chart instance created')
  }
  
  private async testBasicSubscription() {
    console.log('\n1️⃣ Testing Basic Subscription...')
    
    const subscriptionId = BASELINE_SUBSCRIPTION_IDS.YES['1H']
    console.log(`   Using subscription ID: ${subscriptionId}`)
    
    const lineSeries = new LineSeries({
      chartInstance: this.chartInstance!,
      seriesType: 'YES',
      subscriptionId
    })
    
    // Give time for subscription to establish
    await this.sleep(100)
    
    console.log(`   ✓ Series created with type: ${lineSeries.getSeriesType()}`)
    console.log(`   ✓ Subscription ID: ${lineSeries.getSubscriptionId()}`)
    console.log(`   ✓ Series API exists: ${!!lineSeries.getSeriesApi()}`)
    
    lineSeries.remove()
    console.log('   ✓ Series cleaned up')
  }
  
  private async testSubscriptionParsing() {
    console.log('\n2️⃣ Testing Subscription ID Parsing...')
    
    const testCases = [
      { id: BASELINE_SUBSCRIPTION_IDS.YES['1H'], type: 'YES', expected: { market: 'MARKET', side: 'yes', range: '1H' } },
      { id: BASELINE_SUBSCRIPTION_IDS.NO['1W'], type: 'NO', expected: { market: 'MARKET', side: 'no', range: '1W' } },
      { id: BASELINE_SUBSCRIPTION_IDS.YES['1M'], type: 'YES', expected: { market: 'MARKET', side: 'yes', range: '1M' } },
      { id: BASELINE_SUBSCRIPTION_IDS.NO['1Y'], type: 'NO', expected: { market: 'MARKET', side: 'no', range: '1Y' } }
    ]
    
    for (const testCase of testCases) {
      console.log(`   Testing: ${testCase.id} (${testCase.type})`)
      
      const series = new LineSeries({
        chartInstance: this.chartInstance!,
        seriesType: testCase.type as any,
        subscriptionId: testCase.id
      })
      
      await this.sleep(50)
      
      // Parse the subscription ID the same way the series does
      const parts = testCase.id.split('&')
      if (parts.length >= 3) {
        const [seriesTypeStr, timeRange, ...marketIdParts] = parts
        const marketId = marketIdParts.join('&') // Rejoin market ID parts that may contain '&'
        console.log(`   ✓ Parsed: market=${marketId}, side=${seriesTypeStr}, range=${timeRange}`)
        
        // Verify parsing matches expectations
        if (marketId !== testCase.expected.market || 
            seriesTypeStr !== testCase.expected.side || 
            timeRange !== testCase.expected.range) {
          throw new Error(`Parsing mismatch for ${testCase.id}`)
        }
      } else {
        throw new Error(`Invalid subscription ID format: ${testCase.id}`)
      }
      
      series.remove()
    }
    
    console.log('   ✓ All subscription ID parsing tests passed')
  }
  
  private async testRangeSwitch() {
    console.log('\n3️⃣ Testing Range Switching...')
    
    const initialId = BASELINE_SUBSCRIPTION_IDS.YES['1H']
    
    const series = new LineSeries({
      chartInstance: this.chartInstance!,
      seriesType: 'YES',
      subscriptionId: initialId
    })
    
    await this.sleep(100)
    
    console.log(`   Initial subscription: ${series.getSubscriptionId()}`)
    
    // Mock the getNewSubscriptionId function
    const mockGetNewSubscriptionId = (seriesType: 'YES' | 'NO', range: string): string => {
      return BASELINE_SUBSCRIPTION_IDS[seriesType][range as '1H' | '1W' | '1M' | '1Y']
    }
    
    // Switch to 1W
    console.log('   Switching to 1W range...')
    await series.setRange('1W', mockGetNewSubscriptionId)
    await this.sleep(200)
    
    const expectedNewId = BASELINE_SUBSCRIPTION_IDS.YES['1W']
    console.log(`   New subscription: ${series.getSubscriptionId()}`)
    console.log(`   Expected: ${expectedNewId}`)
    
    if (series.getSubscriptionId() !== expectedNewId) {
      throw new Error(`Range switch failed. Expected ${expectedNewId}, got ${series.getSubscriptionId()}`)
    }
    
    console.log('   ✓ Range switch successful')
    
    series.remove()
  }
  
  private async testMultipleSeries() {
    console.log('\n4️⃣ Testing Multiple Series...')
    
    const series1 = new LineSeries({
      chartInstance: this.chartInstance!,
      seriesType: 'YES',
      subscriptionId: BASELINE_SUBSCRIPTION_IDS.YES['1H']
    })
    
    const series2 = new MovingAverage({
      chartInstance: this.chartInstance!,
      seriesType: 'NO',
      subscriptionId: BASELINE_SUBSCRIPTION_IDS.NO['1H']
    })
    
    await this.sleep(200)
    
    console.log(`   Series 1: ${series1.getSeriesType()} - ${series1.getSubscriptionId()}`)
    console.log(`   Series 2: ${series2.getSeriesType()} - ${series2.getSubscriptionId()}`)
    
    if (!series1.getSeriesApi() || !series2.getSeriesApi()) {
      throw new Error('One or more series failed to create properly')
    }
    
    console.log('   ✓ Multiple series created successfully')
    
    series1.remove()
    series2.remove()
  }
  
  private async testErrorHandling() {
    console.log('\n5️⃣ Testing Error Handling...')
    
    // Test invalid subscription ID
    console.log('   Testing invalid subscription ID...')
    const series1 = new LineSeries({
      chartInstance: this.chartInstance!,
      seriesType: 'YES',
      subscriptionId: 'invalid_format'
    })
    
    await this.sleep(100)
    
    if (!series1.getSeriesApi()) {
      throw new Error('Series should still be created even with invalid subscription ID')
    }
    
    console.log('   ✓ Invalid subscription ID handled gracefully')
    series1.remove()
    
    // Test missing subscription ID
    console.log('   Testing missing subscription ID...')
    const series2 = new LineSeries({
      chartInstance: this.chartInstance!,
      seriesType: 'YES'
      // No subscriptionId
    })
    
    await this.sleep(100)
    
    if (!series2.getSeriesApi()) {
      throw new Error('Series should still be created even without subscription ID')
    }
    
    console.log('   ✓ Missing subscription ID handled gracefully')
    series2.remove()
  }
  
  private async sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }
  
  private cleanup() {
    console.log('\n🧹 Cleaning up...')
    
    if (this.chartInstance) {
      this.chartInstance.remove()
      this.chartInstance = null
    }
    
    // Clear any remaining subscriptions  
    // Note: RxJSChannelManager doesn't have unsubscribeAll method
    
    console.log('✅ Cleanup complete')
  }
}

// Run the tests if this file is executed directly
if (require.main === module) {
  const runner = new SubscriptionTestRunner()
  runner.runTests().catch(error => {
    console.error('❌ Test runner failed:', error)
    process.exit(1)
  })
}

export { SubscriptionTestRunner }