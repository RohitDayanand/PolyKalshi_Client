import type { Market } from '@/types/market'

// Type definitions
export interface CachedMarket {
  id: string
  title: string
  slug: string
  category: string
  volume: number
  liquidity: number
  active: boolean
  clobTokenIds?: string[]
  outcomes?: Array<{
    name: string
    tokenId: string
    price: number
  }>
  lastUpdated: string
  platform: 'polymarket' | 'kalshi'
}

// Custom search configuration
export interface SearchConfig {
  maxResults: number
  enableFuzzySearch: boolean
  minVolumeThreshold?: number
  clobApiUrl?: string
}

export const defaultConfig: SearchConfig = {
  maxResults: 50,
  enableFuzzySearch: true,
  minVolumeThreshold: 1000,
  clobApiUrl: 'https://clob.polymarket.com'
}

// Base search service interface
export interface BaseSearchService {
  searchQuestions(query: string): Promise<Market[]>
  generateQuestions(query: string): Promise<Market[]>
  updateConfig(newConfig: Partial<SearchConfig>): void
  getConfig(): SearchConfig
}