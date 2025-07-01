/**
 * Quick test for AdaptiveChart component with platform and marketId props
 */

import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { AdaptiveChart } from '../AdaptiveChart'

// Mock the hooks since they depend on Redux store
jest.mock('../../useChartInstance', () => ({
  useChartInstance: () => ({
    chartContainerRef: { current: null },
    chartInstanceRef: { current: null },
    handleViewChange: jest.fn(),
    seriesRef: { current: { yes: null, no: null } }
  })
}))

jest.mock('../../useOverlayManager', () => ({
  useOverlayManager: () => ({
    getActiveOverlays: jest.fn().mockReturnValue([]),
    getOverlayInstance: jest.fn(),
    activeOverlayCount: 0
  })
}))

jest.mock('../../hooks/useChartViewState', () => ({
  useChartViewState: () => ({
    selectedView: 'BOTH',
    setView: jest.fn()
  })
}))

jest.mock('../../hooks/useChartRangeState', () => ({
  useChartRangeState: () => ({
    selectedRange: '1H',
    setRange: jest.fn()
  })
}))

jest.mock('../../hooks/useChartFullscreenState', () => ({
  useChartFullscreenState: () => ({
    isFullscreen: false,
    setFullscreen: jest.fn()
  })
}))

// Mock ChartControls and OverlayToggle components
jest.mock('../ChartControls', () => ({
  ChartControls: ({ chartId }: { chartId: string }) => (
    <div data-testid="chart-controls">Chart Controls for {chartId}</div>
  )
}))

jest.mock('../OverlayToggle', () => ({
  OverlayToggle: () => <div data-testid="overlay-toggle">Overlay Toggle</div>
}))

// Create a minimal Redux store for testing
const createTestStore = () => configureStore({
  reducer: {
    // Add minimal reducers if needed
    test: (state = {}) => state
  }
})

describe('AdaptiveChart Component', () => {
  const defaultProps = {
    isVisible: true,
    showControls: true,
    containerHeight: 400,
    className: 'test-chart',
    staticData: { yes: [], no: [] },
    setStaticData: jest.fn(),
    chartId: 'test-chart-id'
  }

  beforeEach(() => {
    // Clear console.log mock before each test
    jest.clearAllMocks()
    // Mock console.log to capture debug messages
    jest.spyOn(console, 'log').mockImplementation(() => {})
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('should render without crashing', () => {
    const store = createTestStore()
    
    render(
      <Provider store={store}>
        <AdaptiveChart {...defaultProps} />
      </Provider>
    )

    expect(screen.getByTestId('chart-controls')).toBeInTheDocument()
  })

  it('should accept and log platform and marketId props', () => {
    const store = createTestStore()
    const consoleLogSpy = jest.spyOn(console, 'log')

    const propsWithMarket = {
      ...defaultProps,
      platform: 'kalshi',
      marketId: 'kalshi_PRES-DEM-2024',
      marketTitle: 'Will Democrats win the 2024 Presidential Election?'
    }

    render(
      <Provider store={store}>
        <AdaptiveChart {...propsWithMarket} />
      </Provider>
    )

    // Check that the debug console.log was called with the correct market data
    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.stringContaining('📈 AdaptiveChart [test-chart-id]: Received market data')
    )
    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.stringContaining('Platform: kalshi')
    )
    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.stringContaining('Market ID: kalshi_PRES-DEM-2024')
    )
    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.stringContaining('Title: Will Democrats win the 2024 Presidential Election?')
    )
  })

  it('should handle missing platform/marketId gracefully', () => {
    const store = createTestStore()
    const consoleLogSpy = jest.spyOn(console, 'log')

    render(
      <Provider store={store}>
        <AdaptiveChart {...defaultProps} />
      </Provider>
    )

    // Should not log market data if platform/marketId are missing
    expect(consoleLogSpy).not.toHaveBeenCalledWith(
      expect.stringContaining('📈 AdaptiveChart [test-chart-id]: Received market data')
    )
  })

  it('should pass platform and marketId to useChartInstance hook', () => {
    const store = createTestStore()
    const useChartInstanceMock = require('../../useChartInstance').useChartInstance

    const propsWithMarket = {
      ...defaultProps,
      platform: 'polymarket',
      marketId: 'polymarket_123456789'
    }

    render(
      <Provider store={store}>
        <AdaptiveChart {...propsWithMarket} />
      </Provider>
    )

    // Verify that useChartInstance was called with the correct props
    expect(useChartInstanceMock).toHaveBeenCalledWith(
      expect.objectContaining({
        platform: 'polymarket',
        marketId: 'polymarket_123456789',
        chartId: 'test-chart-id'
      })
    )
  })

  it('should render chart controls when showControls is true', () => {
    const store = createTestStore()

    render(
      <Provider store={store}>
        <AdaptiveChart {...defaultProps} showControls={true} />
      </Provider>
    )

    expect(screen.getByTestId('chart-controls')).toBeInTheDocument()
    expect(screen.getByText('Chart Controls for test-chart-id')).toBeInTheDocument()
  })

  it('should not render chart controls when showControls is false', () => {
    const store = createTestStore()

    render(
      <Provider store={store}>
        <AdaptiveChart {...defaultProps} showControls={false} />
      </Provider>
    )

    expect(screen.queryByTestId('chart-controls')).not.toBeInTheDocument()
  })

  it('should display debug info with market data', () => {
    const store = createTestStore()

    const propsWithMarket = {
      ...defaultProps,
      platform: 'kalshi',
      marketId: 'kalshi_PRES-DEM-2024'
    }

    render(
      <Provider store={store}>
        <AdaptiveChart {...propsWithMarket} />
      </Provider>
    )

    // Check that debug info is displayed
    expect(screen.getByText(/Check browser console for debugging info/)).toBeInTheDocument()
    expect(screen.getByText(/Container: 400px/)).toBeInTheDocument()
  })
})
