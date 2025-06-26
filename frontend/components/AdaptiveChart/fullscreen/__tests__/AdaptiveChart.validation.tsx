/**
 * Quick TypeScript validation test for AdaptiveChart props
 * This validates that the component accepts the new props without runtime testing
 */

import React from 'react'
import { AdaptiveChart } from '../AdaptiveChart'

// Mock data for testing
const mockStaticData = { yes: [], no: [] }
const mockSetStaticData = (data: { yes: any[], no: any[] }) => {}

/**
 * Test 1: Component should accept all props including new platform/marketId
 */
function testComponentPropsAcceptance() {
  console.log('🧪 Test 1: Component Props Acceptance')
  
  // This should compile without TypeScript errors
  const validPropsTest = (
    <AdaptiveChart
      isVisible={true}
      showControls={true}
      containerHeight={400}
      className="test-chart"
      staticData={mockStaticData}
      setStaticData={mockSetStaticData}
      chartId="test-chart-1"
      platform="kalshi"
      marketId="kalshi_PRES-DEM-2024"
      marketTitle="Will Democrats win the 2024 Presidential Election?"
    />
  )
  
  console.log('✅ Component accepts all props including platform, marketId, and marketTitle')
  return true
}

/**
 * Test 2: Component should work with optional props missing
 */
function testOptionalProps() {
  console.log('🧪 Test 2: Optional Props')
  
  // This should also compile without TypeScript errors
  const minimalPropsTest = (
    <AdaptiveChart
      isVisible={true}
      staticData={mockStaticData}
      setStaticData={mockSetStaticData}
      chartId="test-chart-2"
      // platform, marketId, marketTitle are optional
    />
  )
  
  console.log('✅ Component works with optional props missing')
  return true
}

/**
 * Test 3: Type validation for platform prop
 */
function testPlatformTypeValidation() {
  console.log('🧪 Test 3: Platform Type Validation')
  
  // Valid platform values
  const kalshiTest = (
    <AdaptiveChart
      isVisible={true}
      staticData={mockStaticData}
      setStaticData={mockSetStaticData}
      chartId="test-chart-3a"
      platform="kalshi"
    />
  )
  
  const polymarketTest = (
    <AdaptiveChart
      isVisible={true}
      staticData={mockStaticData}
      setStaticData={mockSetStaticData}
      chartId="test-chart-3b"
      platform="polymarket"
    />
  )
  
  console.log('✅ Platform prop accepts "kalshi" and "polymarket" values')
  return true
}

/**
 * Test 4: Market ID format validation
 */
function testMarketIdFormats() {
  console.log('🧪 Test 4: Market ID Formats')
  
  const kalshiMarketId = (
    <AdaptiveChart
      isVisible={true}
      staticData={mockStaticData}
      setStaticData={mockSetStaticData}
      chartId="test-chart-4a"
      platform="kalshi"
      marketId="kalshi_PRES-DEM-2024"
    />
  )
  
  const polymarketMarketId = (
    <AdaptiveChart
      isVisible={true}
      staticData={mockStaticData}
      setStaticData={mockSetStaticData}
      chartId="test-chart-4b"
      platform="polymarket"
      marketId="polymarket_123456789012345678901234567890"
    />
  )
  
  console.log('✅ MarketId prop accepts different format strings')
  return true
}

/**
 * Test 5: Real-world usage scenarios
 */
function testRealWorldScenarios() {
  console.log('🧪 Test 5: Real-World Usage Scenarios')
  
  // Scenario 1: Market selection in visualization panel
  const market1Scenario = (
    <AdaptiveChart
      isVisible={true}
      showControls={true}
      containerHeight={500}
      className="market-1-chart w-full h-full"
      staticData={mockStaticData}
      setStaticData={mockSetStaticData}
      chartId="market-1"
      platform="kalshi"
      marketId="kalshi_PRES-DEM-2024"
      marketTitle="Will Democrats win the 2024 Presidential Election?"
    />
  )
  
  // Scenario 2: Market selection for comparison
  const comparisonScenario = (
    <AdaptiveChart
      isVisible={true}
      showControls={true}
      containerHeight={500}
      className="comparison-chart w-full h-full"
      staticData={mockStaticData}
      setStaticData={mockSetStaticData}
      chartId="comparison"
      platform="polymarket"
      marketId="polymarket_987654321098765432109876543210"
      marketTitle="2024 US Presidential Election Winner"
    />
  )
  
  console.log('✅ Real-world scenarios compile correctly')
  return true
}

/**
 * Run all tests
 */
export function runAdaptiveChartTests() {
  console.log('🚀 Starting AdaptiveChart Component Tests...\n')
  
  try {
    testComponentPropsAcceptance()
    testOptionalProps()
    testPlatformTypeValidation()
    testMarketIdFormats()
    testRealWorldScenarios()
    
    console.log('\n🎉 All tests passed! AdaptiveChart component properly accepts platform, marketId, and marketTitle props.')
    return true
  } catch (error) {
    console.error('❌ Test failed:', error)
    return false
  }
}

// Export component configurations for validation
export const testConfigurations = {
  kalshiMarket: {
    isVisible: true,
    showControls: true,
    containerHeight: 500,
    className: "kalshi-chart",
    chartId: "kalshi-test",
    platform: "kalshi" as const,
    marketId: "kalshi_PRES-DEM-2024",
    marketTitle: "Will Democrats win the 2024 Presidential Election?"
  },
  
  polymarketMarket: {
    isVisible: true,
    showControls: true,
    containerHeight: 500,
    className: "polymarket-chart", 
    chartId: "polymarket-test",
    platform: "polymarket" as const,
    marketId: "polymarket_123456789012345678901234567890",
    marketTitle: "2024 US Presidential Election Winner"
  },
  
  minimal: {
    isVisible: true,
    staticData: mockStaticData,
    setStaticData: mockSetStaticData,
    chartId: "minimal-test"
  }
}

// Run tests if this file is executed directly
if (typeof window === 'undefined') {
  runAdaptiveChartTests()
}
