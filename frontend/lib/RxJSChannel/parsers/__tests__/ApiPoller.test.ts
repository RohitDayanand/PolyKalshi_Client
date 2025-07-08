import { Subject } from 'rxjs'
import { ApiPoller } from '../../ApiPoller'
import { ChannelCache } from '../../ChannelCache'
import { ChannelConfig, ChannelMessage, DataPoint } from '../../types'
import { DefaultParserFactory } from '../ParserFactory'
import { KalshiParser } from '../KalshiParser'
import { PolymarketParser } from '../PolymarketParser'

// Mock fetch
global.fetch = jest.fn()

describe('ApiPoller with Parsers', () => {
  let apiPoller: ApiPoller
  let channelSubject: Subject<ChannelMessage>
  let channelCache: ChannelCache
  let mockChannelConfig: ChannelConfig

  beforeEach(() => {
    channelSubject = new Subject<ChannelMessage>()
    channelCache = new ChannelCache()
    apiPoller = new ApiPoller(channelSubject, channelCache, 300, 100)
    
    mockChannelConfig = {
      marketId: 'TEST-123',
      side: 'yes',
      range: '1H',
      platform: 'kalshi',
      lruCache: {} as any,
      lastEmitTime: 0,
      throttleMs: 1000,
      lastApiPoll: 0,
      apiPollInterval: 5000,
      isPolling: false,
      subscriberCount: 0
    }

    // Clear all mocks
    jest.clearAllMocks()
  })

  afterEach(() => {
    apiPoller.destroy()
  })

  describe('fetchInitialData', () => {
    it('should use KalshiParser for kalshi platform', async () => {
      const mockResponse = {
        success: true,
        data: {
          candlesticks: [
            {
              time: 1640995200,
              yes_price: 0.75,
              yes_open: 0.70,
              yes_high: 0.80,
              yes_low: 0.65,
              yes_close: 0.75,
              volume: 1000
            }
          ]
        }
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const channelKey = 'kalshi:TEST-123:yes:1H'
      const emittedMessages: ChannelMessage[] = []
      
      channelSubject.subscribe(message => {
        emittedMessages.push(message)
      })

      await apiPoller.fetchInitialData(channelKey, mockChannelConfig)

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('http://localhost:8000/api/kalshi/candlesticks')
      )
      expect(emittedMessages).toHaveLength(1)
      expect(emittedMessages[0].updateType).toBe('initial_data')
      expect(emittedMessages[0].data).toHaveLength(1)
    })

    it('should use PolymarketParser for polymarket platform', async () => {
      mockChannelConfig.platform = 'polymarket'
      
      const mockResponse = {
        success: true,
        data: {
          candlesticks: [
            {
              time: 1640995200,
              yes_price: 0.65,
              yes_open: 0.60,
              yes_high: 0.70,
              yes_low: 0.55,
              yes_close: 0.65,
              volume: 800
            }
          ]
        }
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const channelKey = 'polymarket:TEST-123:yes:1H'
      const emittedMessages: ChannelMessage[] = []
      
      channelSubject.subscribe(message => {
        emittedMessages.push(message)
      })

      await apiPoller.fetchInitialData(channelKey, mockChannelConfig)

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('http://localhost:8000/api/polymarket/candlesticks')
      )
      expect(emittedMessages).toHaveLength(1)
      expect(emittedMessages[0].updateType).toBe('initial_data')
    })

    it('should handle API errors gracefully', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error'
      })

      const channelKey = 'kalshi:TEST-123:yes:1H'
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation()

      await apiPoller.fetchInitialData(channelKey, mockChannelConfig)

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Failed to fetch initial history'),
        expect.any(Error)
      )
      
      consoleSpy.mockRestore()
    })

    it('should handle unsuccessful API response', async () => {
      const mockResponse = {
        success: false,
        error: 'Market not found'
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const channelKey = 'kalshi:TEST-123:yes:1H'
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation()

      await apiPoller.fetchInitialData(channelKey, mockChannelConfig)

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Failed to fetch initial history'),
        expect.any(Error)
      )
      
      consoleSpy.mockRestore()
    })
  })

  describe('parser factory integration', () => {
    it('should create appropriate parser for each platform', () => {
      const factory = new DefaultParserFactory()
      
      const kalshiParser = factory.createParser('kalshi')
      const polymarketParser = factory.createParser('polymarket')
      
      expect(kalshiParser).toBeInstanceOf(KalshiParser)
      expect(polymarketParser).toBeInstanceOf(PolymarketParser)
    })
  })

  describe('polling behavior', () => {
    it('should start polling after successful initial data fetch', async () => {
      const mockResponse = {
        success: true,
        data: {
          candlesticks: [
            {
              time: 1640995200,
              yes_price: 0.75,
              yes_open: 0.70,
              yes_high: 0.80,
              yes_low: 0.65,
              yes_close: 0.75,
              volume: 1000
            }
          ]
        }
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const channelKey = 'kalshi:TEST-123:yes:1H'

      await apiPoller.fetchInitialData(channelKey, mockChannelConfig)

      expect(mockChannelConfig.isPolling).toBe(true)
    })

    it('should stop polling when requested', async () => {
      mockChannelConfig.isPolling = true
      const channelKey = 'kalshi:TEST-123:yes:1H'

      apiPoller.stopPolling(channelKey, mockChannelConfig)

      expect(mockChannelConfig.isPolling).toBe(false)
    })
  })

  describe('stats', () => {
    it('should return correct stats', () => {
      const stats = apiPoller.getStats()
      
      expect(stats).toEqual({
        activePolls: 0,
        maxCacheSize: 300
      })
    })
  })
})