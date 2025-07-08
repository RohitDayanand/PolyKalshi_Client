import { KalshiParser } from '../KalshiParser'
import { ChannelConfig, MarketSide } from '../../types'
import { ApiResponse } from '../types'

describe('KalshiParser', () => {
  let parser: KalshiParser
  let mockChannelConfig: ChannelConfig

  beforeEach(() => {
    parser = new KalshiParser()
    mockChannelConfig = {
      marketId: 'TEST-123',
      side: 'yes' as MarketSide,
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
  })

  describe('platform property', () => {
    it('should return kalshi as platform', () => {
      expect(parser.platform).toBe('kalshi')
    })
  })

  describe('buildApiUrl', () => {
    it('should build initial data URL correctly', () => {
      const url = parser.buildApiUrl(mockChannelConfig, 'initial')
      
      expect(url).toContain('http://localhost:8000/api/kalshi/candlesticks')
      expect(url).toContain('market_string_id=TEST-123%26yes%261H')
      expect(url).toContain('start_ts=')
      expect(url).toContain('end_ts=')
    })

    it('should build update URL with since parameter', () => {
      const since = Date.now() - 1000
      const url = parser.buildApiUrl(mockChannelConfig, 'update', since)
      
      expect(url).toContain('http://localhost:8000/api/kalshi/candlesticks')
      expect(url).toContain(`start_ts=${Math.floor(since / 1000)}`)
    })

    it('should handle different market sides', () => {
      mockChannelConfig.side = 'no'
      const url = parser.buildApiUrl(mockChannelConfig, 'initial')
      
      expect(url).toContain('market_string_id=TEST-123%26no%261H')
    })
  })

  describe('parseHistoricalData', () => {
    it('should parse candlestick data correctly', () => {
      const mockResponse: ApiResponse = {
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
            },
            {
              time: 1640995260,
              yes_price: 0.78,
              yes_open: 0.75,
              yes_high: 0.82,
              yes_low: 0.73,
              yes_close: 0.78,
              volume: 1200
            }
          ]
        }
      }

      const result = parser.parseHistoricalData(mockResponse, 'yes')

      expect(result).toHaveLength(2)
      expect(result[0]).toEqual({
        time: 1640995200,
        value: 0.75,
        volume: 1000,
        candlestick: {
          time: 1640995200,
          open: 0.70,
          high: 0.80,
          low: 0.65,
          close: 0.75
        }
      })
    })

    it('should handle no side data correctly', () => {
      const mockResponse: ApiResponse = {
        success: true,
        data: {
          candlesticks: [
            {
              time: 1640995200,
              no_price: 0.25,
              no_open: 0.30,
              no_high: 0.35,
              no_low: 0.20,
              no_close: 0.25,
              volume: 500
            }
          ]
        }
      }

      const result = parser.parseHistoricalData(mockResponse, 'no')

      expect(result).toHaveLength(1)
      expect(result[0].value).toBe(0.25)
      expect(result[0].candlestick?.open).toBe(0.30)
    })

    it('should return empty array when no candlesticks data', () => {
      const mockResponse: ApiResponse = {
        success: true,
        data: {}
      }

      const result = parser.parseHistoricalData(mockResponse, 'yes')

      expect(result).toEqual([])
    })

    it('should return empty array when no data', () => {
      const mockResponse: ApiResponse = {
        success: true
      }

      const result = parser.parseHistoricalData(mockResponse, 'yes')

      expect(result).toEqual([])
    })
  })

  describe('calculateTimeRange', () => {
    const now = Date.now()
    const nowTs = Math.floor(now / 1000)

    beforeEach(() => {
      jest.spyOn(Date, 'now').mockReturnValue(now)
    })

    afterEach(() => {
      jest.restoreAllMocks()
    })

    it('should calculate 1H range correctly', () => {
      const result = parser.calculateTimeRange('1H', 'initial')
      
      expect(result.endTs).toBe(nowTs)
      expect(result.startTs).toBe(nowTs - (60 * 60 * 6)) // 6 hours ago
    })

    it('should calculate 1W range correctly', () => {
      const result = parser.calculateTimeRange('1W', 'initial')
      
      expect(result.endTs).toBe(nowTs)
      expect(result.startTs).toBe(nowTs - (7 * 24 * 60 * 60 * 2)) // 2 weeks ago
    })

    it('should calculate 1M range correctly', () => {
      const result = parser.calculateTimeRange('1M', 'initial')
      
      expect(result.endTs).toBe(nowTs)
      expect(result.startTs).toBe(nowTs - (30 * 24 * 60 * 60 * 6)) // 6 months ago
    })

    it('should calculate 1Y range correctly', () => {
      const result = parser.calculateTimeRange('1Y', 'initial')
      
      expect(result.endTs).toBe(nowTs)
      expect(result.startTs).toBe(nowTs - (365 * 24 * 60 * 60)) // 1 year ago
    })

    it('should use since parameter for update type', () => {
      const since = now - 5000
      const result = parser.calculateTimeRange('1H', 'update', since)
      
      expect(result.startTs).toBe(Math.floor(since / 1000))
      expect(result.endTs).toBe(nowTs)
    })

    it('should default to 1 hour for unknown range', () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation()
      
      const result = parser.calculateTimeRange('UNKNOWN', 'initial')
      
      expect(result.startTs).toBe(nowTs - (60 * 60))
      expect(consoleSpy).toHaveBeenCalledWith('Unknown range UNKNOWN, defaulting to 1 hour')
      
      consoleSpy.mockRestore()
    })
  })
})