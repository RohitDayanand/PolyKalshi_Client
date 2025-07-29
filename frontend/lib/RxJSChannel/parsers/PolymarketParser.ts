import { DataPoint, ChannelConfig, MarketSide } from '../types'
import { PlatformParser, ApiResponse } from './types'
import { calculatePolymarketTimeRange } from '../utils/timestampRounding'

export class PolymarketParser implements PlatformParser {
  readonly platform = 'polymarket' as const

  //TODO - to stay idiomatic, all of these external api calls should route through a next.js api route
  buildApiUrl(channelConfig: ChannelConfig, type: 'initial' | 'update', since?: number): string {
    const baseUrl = 'http://localhost:8000/api/polymarket/timeseries'
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
      console.warn('No candlesticks data in Polymarket response')
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
    
    if (type === 'update' && since) {
      // For updates, use the provided since timestamp as start and current as end
      return {
        startTs: Math.floor(since / 1000),
        endTs: nowTs
      }
    } else {
      // For initial requests, use rounded timestamps to prevent append errors
      return calculatePolymarketTimeRange(range, nowTs)
    }
  }
}