import { DataPoint, ChannelConfig, MarketSide } from '../types'
import { PlatformParser, ApiResponse } from './types'

export class KalshiParser implements PlatformParser {
  readonly platform = 'kalshi' as const

  buildApiUrl(channelConfig: ChannelConfig, type: 'initial' | 'update', since?: number): string {
    const baseUrl = 'http://localhost:8000/api/kalshi/candlesticks'
    const marketStringId = `${channelConfig.marketId}&${channelConfig.side}&${channelConfig.range}`
    
    const { startTs, endTs } = this.calculateTimeRange(channelConfig.range, type, since)
    
    const params = new URLSearchParams({
      market_string_id: marketStringId,
      start_ts: startTs.toString(),
      end_ts: endTs.toString()
    })

    return `${baseUrl}?${params.toString()}`
  }

  parseHistoricalData(response: ApiResponse, side: MarketSide): DataPoint[] {
    if (!response.data || !response.data.candlesticks) {
      console.warn('No candlesticks data in Kalshi response')
      return []
    }
    
    const candlesticks = response.data.candlesticks
    
    return candlesticks.map((candle: any) => ({
      time: candle.time,
      value: candle[`${side}_price`],
      volume: candle.volume,
      candlestick: {
        time: candle.time, 
        open: candle[`${side}_open`],
        high: candle[`${side}_high`],
        low: candle[`${side}_low`],
        close: candle[`${side}_close`]
      }
    }))
  }

  calculateTimeRange(range: string, type: 'initial' | 'update', since?: number): { startTs: number, endTs: number } {
    const nowTs = Math.floor(Date.now() / 1000)
    const endTs = nowTs
    
    let startTs: number
    
    if (type === 'update' && since) {
      startTs = Math.floor(since / 1000)
    } else {
      switch (range) {
        case '1H':
          startTs = nowTs - (60 * 60 * 6)
          break
        case '1W':
          startTs = nowTs - (7 * 24 * 60 * 60 * 2)
          break
        case '1M':
          startTs = nowTs - (30 * 24 * 60 * 60 * 6)
          break
        case '1Y':
          startTs = nowTs - (365 * 24 * 60 * 60)
          break
        default:
          console.warn(`Unknown range ${range}, defaulting to 1 hour`)
          startTs = nowTs - (60 * 60)
      }
    }
    
    return { startTs, endTs }
  }
}