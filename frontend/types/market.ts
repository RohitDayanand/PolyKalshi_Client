export interface Market {
  id: string
  title: string
  category: string
  volume: number
  liquidity?: number
  price?: number
  platform?: "polymarket" | "kalshi"
}

export interface SearchResults {
  polymarket: Market[]
  kalshi: Market[]
  loading: boolean
}
