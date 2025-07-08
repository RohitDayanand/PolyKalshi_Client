import { DataPoint, ChannelConfig, MarketSide, Platform } from '../types'

export interface ApiResponse {
  success: boolean
  data?: any
  error?: string
}

export interface PlatformParser {
  readonly platform: Platform
  
  buildApiUrl(channelConfig: ChannelConfig, type: 'initial' | 'update', since?: number): string
  
  parseHistoricalData(response: ApiResponse, side: MarketSide): DataPoint[]
  
  calculateTimeRange(range: string, type: 'initial' | 'update', since?: number): { startTs: number, endTs: number }
}

export interface ParserFactory {
  createParser(platform: Platform): PlatformParser
}