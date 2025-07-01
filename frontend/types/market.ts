export interface Market {
  id: string
  title: string
  category: string
  volume: number
  liquidity?: number
  price?: number
  platform?: "polymarket" | "kalshi"
  lastUpdated?: string
  // For backend tracking only (not for display):
  tokenIds?: string[] // Polymarket: clobTokenIds
  kalshiTicker?: string // Kalshi: e.g. "KXPRESPOLAND-NT"
}

export interface SearchResults {
  polymarket: Market[]
  kalshi: Market[]
  loading: boolean
}
