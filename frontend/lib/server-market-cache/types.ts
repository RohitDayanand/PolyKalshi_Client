// Shared types for server market cache
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

export interface SelectedToken {
  marketId: string
  marketTitle: string
  tokenId: string
  outcomeName: string
  selectedAt: string
  platform: 'polymarket' | 'kalshi'
}

export interface CacheStats {
  marketCount: number
  selectedTokenCount: number
  lastUpdate: string
  cacheAge: number
  isStale: boolean
}