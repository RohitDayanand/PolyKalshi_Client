import { TimeRange as ChartTimeRange } from '../ChartStuff/chart-types'
import { LRUCache } from 'lru-cache'
import { Observable } from 'rxjs'

export type TimeRange = ChartTimeRange
export type MarketSide = 'yes' | 'no'
export type UpdateType = 'initial_data' | 'update'
export type Platform = 'polymarket' | 'kalshi'

/*
* DataPoint interface with optional volume value for volume data points - charts will 
* only extract what they need 
*/
export interface DataPoint {
  time: number
  value: number
  volume?: number
  candlestick?: OHLC
}

export interface TickerData {
  type: 'ticker_update'
  market_id: string
  platform: Platform
  summary_stats: {
    yes?: { bid: number; ask: number; volume: number }
    no?: { bid: number; ask: number; volume: number },
    candlestick?: {
      yes_open: number,
      no_open: number,
      yes_close: number,
      no_close: number,
      yes_high: number,
      no_high: number,
      yes_low: number,
      no_low: number,
      time: number
    }
  }
  timestamp: number
}

export interface OHLC {
  time: number | null,
  open: number | null,
  high: number | null,
  low: number | null,
  close: number | null,

}

export interface ChannelMessage {
  channel: string
  updateType: UpdateType
  data: DataPoint | DataPoint[]
  candlestick?: OHLC | OHLC[]
}

/*
* Has all of the data of the channel calling
* @params include marketId, side, range, platform, cache
*/
export interface ChannelConfig {
  /*
  * Has all of the details of the Channel Calling 
  * @params
  */
  marketId: string
  side: MarketSide
  range: TimeRange
  platform: Platform
  lruCache: LRUCache<number, DataPoint>
  lastEmitTime: number
  throttleMs: number
  lastApiPoll: number
  apiPollInterval: number
  isPolling: boolean
  // Observable reuse fields
  sharedObservable?: Observable<ChannelMessage>
  subscriberCount: number
}

export interface ChannelStats {
  channelKey: string
  marketId: string
  side: MarketSide
  range: TimeRange
  platform: Platform
  cacheSize: number
  lruCacheSize: number
  throttleMs: number
  lastEmitTime: number
  lastApiPoll: number
  isPolling: boolean
}

export interface ManagerStats {
  totalChannels: number
  activeChannels: number
  totalCacheSize: number
  websocketConnected: boolean
  channels: ChannelStats[]
}

export interface ChannelKey {
  marketId: string
  side: MarketSide
  range: TimeRange
}