"use client"

import { useState, useMemo, useEffect } from "react"
import { useAppSelector } from "@/lib/store/hooks"
import { selectSubscriptions } from "@/lib/store/apiSubscriptionSlice"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { PriceChart } from "@/components/charts/price-chart"
import { OrderbookChart } from "@/components/charts/orderbook-chart"
import { VolumeChart } from "@/components/charts/volume-chart"
import type { Market } from "@/types/market"
import { AdaptiveChart } from "../AdaptiveChart/fullscreen/AdaptiveChart"

export function VisualizationPanel() {
  const [timeframe, setTimeframe] = useState("24h")
  
  // Load subscribed markets from Redux subscription state
  const subscriptions = useAppSelector(selectSubscriptions)
  const subscribedMarkets = useMemo(() => {
    return Object.entries(subscriptions).map(([, subscription]) => {
      // Strip platform prefix from backend_market_id since it's already included
      const backendId = (subscription as any).backend_market_id
      const cleanId = backendId.replace(/^(polymarket_|kalshi_)/, '')
      
      return {
        id: cleanId,  // Use clean ID without platform prefix
        title: (subscription as any).market_title,
        platform: (subscription as any).platform as "polymarket" | "kalshi",
        category: 'General',
        volume: 0
      }
    })
  }, [subscriptions])
  
  // Individual market selections
  const [market1, setMarket1] = useState<Market | null>(null)
  const [market2, setMarket2] = useState<Market | null>(null)
  
  // Clear selected markets if they're no longer in subscribed markets
  useEffect(() => {
    if (market1 && !subscribedMarkets.find(m => m.id === market1.id)) {
      setMarket1(null)
      setMarket1Data({ yes: [], no: [] })
    }
    if (market2 && !subscribedMarkets.find(m => m.id === market2.id)) {
      setMarket2(null)
      setMarket2Data({ yes: [], no: [] })
    }
  }, [subscribedMarkets, market1, market2])
  
  // Chart type selections for each market
  const [market1ChartType, setMarket1ChartType] = useState("price")
  const [market2ChartType, setMarket2ChartType] = useState("price")
  

  // Chart data states
  const [market1Data, setMarket1Data] = useState<{ yes: any[], no: any[] }>({ yes: [], no: [] })
  const [market2Data, setMarket2Data] = useState<{ yes: any[], no: any[] }>({ yes: [], no: [] })

  if (subscribedMarkets.length === 0) {
    return (
      <Card className="h-full min-h-[800px]">
        <CardContent className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <h3 className="text-lg font-medium">No Markets Available</h3>
            <p className="text-muted-foreground">Subscribe to markets to begin pair visualization</p>
          </div>
        </CardContent>
      </Card>
    )
  }


  return (
    <Card className="h-full min-h-[800px] w-full">
      <CardHeader className="pb-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <CardTitle className="text-xl">Market Pair Visualization</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-8 px-6">        {/* Top Row: Two Market Charts Side by Side */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Market 1 */}
          <Card className="h-[600px] w-full">
            <CardHeader className="pb-2 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-base">Market #1</CardTitle>
                <div className="flex items-center gap-2">
                </div>
              </div>
              <Select value={market1?.id || ""} onValueChange={(value) => {
                const selected = subscribedMarkets.find(m => m.id === value)
                setMarket1(selected || null)
              }}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select Market #1" />
                </SelectTrigger>
                <SelectContent>
                  {subscribedMarkets.map((market) => (
                    <SelectItem key={market.id} value={market.id}>
                      <div className="flex flex-col">
                        <span className="font-medium truncate max-w-[300px]">{market.title}</span>
                        <span className="text-xs text-muted-foreground">{market.platform}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardHeader>
            <CardContent className="h-[500px] p-2">
              {market1 ? (
                <AdaptiveChart
                  isVisible={true}
                  showControls={true}
                  containerHeight={500}
                  className="market-1-chart w-full h-full"
                  staticData={market1Data}
                  setStaticData={setMarket1Data}
                  chartId="market-1"
                  platform={market1.platform}
                  marketId={market1.id}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Select a market to view chart
                </div>
              )}
            </CardContent>
          </Card>

          {/* Market 2 */}
          <Card className="h-[600px] w-full">
            <CardHeader className="pb-2 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-base">Market #2</CardTitle>
                <div className="flex items-center gap-2">
                </div>
              </div>
              <Select value={market2?.id || ""} onValueChange={(value) => {
                const selected = subscribedMarkets.find(m => m.id === value)
                setMarket2(selected || null)
              }}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select Market #2" />
                </SelectTrigger>
                <SelectContent>
                  {subscribedMarkets.map((market) => (
                    <SelectItem key={market.id} value={market.id}>
                      <div className="flex flex-col">
                        <span className="font-medium truncate max-w-[300px]">{market.title}</span>
                        <span className="text-xs text-muted-foreground">{market.platform}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardHeader>
            <CardContent className="h-[500px] p-2">
              {market2 ? (
                <AdaptiveChart
                  isVisible={true}
                  showControls={true}
                  containerHeight={500}
                  className="market-2-chart w-full h-full"
                  staticData={market2Data}
                  setStaticData={setMarket2Data}
                  chartId="market-2"
                  platform={market2.platform}
                  marketId={market2.id}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Select a market to view chart
                </div>
              )}
            </CardContent>
          </Card>
        </div>

      </CardContent>
    </Card>
  )
}
