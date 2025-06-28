import { TimeRange as ChartTimeRange } from '../ChartStuff/chart-types'
import { LRUCache } from 'lru-cache'

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
}

export interface TickerData {
  type: 'ticker_update'
  market_id: string
  platform: Platform
  summary_stats: {
    yes?: { bid: number; ask: number; volume: number }
    no?: { bid: number; ask: number; volume: number }
  }
  timestamp: number
}

export interface ChannelMessage {
  channel: string
  updateType: UpdateType
  data: DataPoint | DataPoint[]
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
  cache: DataPoint[] // Legacy array cache
  lruCache: LRUCache<number, DataPoint>
  lastEmitTime: number
  throttleMs: number
  lastApiPoll: number
  apiPollInterval: number
  isPolling: boolean
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