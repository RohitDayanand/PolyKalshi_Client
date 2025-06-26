"use client"

import { useState, useEffect } from "react"
import { marketSearchService } from "@/lib/search-service"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { PriceChart } from "@/components/charts/price-chart"
import { OrderbookChart } from "@/components/charts/orderbook-chart"
import { VolumeChart } from "@/components/charts/volume-chart"
import { MarketComparison } from "@/components/charts/market-comparison"
import { Button } from "@/components/ui/button"
import { CheckSquare } from "lucide-react"
import type { Market } from "@/types/market"
import { AdaptiveChart } from "./AdaptiveChart/fullscreen/AdaptiveChart"

export function VisualizationPanel() {
  const [subscribedMarkets, setSubscribedMarkets] = useState<Market[]>([])
  const [timeframe, setTimeframe] = useState("24h")
  
  // Load subscribed markets from marketSearchService
  useEffect(() => {
    const loadSubscribedMarkets = async () => {
      try {
        const selectedTokens = await marketSearchService.getSelectedTokens()
        // Convert selected tokens to Market format
        const markets: Market[] = Object.values(selectedTokens).map((token: any) => ({
          id: token.marketId,
          title: token.marketTitle,
          category: 'General',
          volume: 0,
          platform: token.marketId.startsWith('poly_') ? 'polymarket' : 'kalshi'
        }))
        setSubscribedMarkets(markets)
      } catch (error) {
        console.error('Error loading subscribed markets:', error)
      }
    }
    
    loadSubscribedMarkets()
    
    // Optionally refresh every 30 seconds to pick up new subscriptions
    const interval = setInterval(loadSubscribedMarkets, 30000)
    return () => clearInterval(interval)
  }, [])
  
  // Individual market selections
  const [market1, setMarket1] = useState<Market | null>(null)
  const [market2, setMarket2] = useState<Market | null>(null)
  
  // Chart type selections for each market
  const [market1ChartType, setMarket1ChartType] = useState("price")
  const [market2ChartType, setMarket2ChartType] = useState("price")
  
  // Center chart configuration
  const [centerChartType, setCenterChartType] = useState("comparison")

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

  const renderChart = (chartType: string, markets: Market[]) => {
    switch (chartType) {
      case "price":
        return <PriceChart markets={markets} timeframe={timeframe} />
      case "orderbook":
        return <OrderbookChart markets={markets} />
      case "volume":
        return <VolumeChart markets={markets} timeframe={timeframe} />
      case "comparison":
        return <MarketComparison markets={markets} timeframe={timeframe} />
      default:
        return <PriceChart markets={markets} timeframe={timeframe} />
    }
  }

  const centerMarkets = [market1, market2].filter(Boolean) as Market[]

  return (
    <Card className="h-full min-h-[1200px] w-full">
      <CardHeader className="pb-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <CardTitle className="text-xl">Market Pair Visualization</CardTitle>
          <div className="flex items-center gap-2">
            <Select value={timeframe} onValueChange={setTimeframe}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Timeframe" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1h">1 Hour</SelectItem>
                <SelectItem value="24h">24 Hours</SelectItem>
                <SelectItem value="7d">7 Days</SelectItem>
                <SelectItem value="30d">30 Days</SelectItem>
              </SelectContent>
            </Select>
          </div>
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
                  <Select value={market1ChartType} onValueChange={setMarket1ChartType}>
                    <SelectTrigger className="w-[100px] h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="price">Price</SelectItem>
                      <SelectItem value="orderbook">Orderbook</SelectItem>
                      <SelectItem value="volume">Volume</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Select value={market1?.id || ""} onValueChange={(value) => {
                const selected = subscribedMarkets.find(m => m.id === value)
                console.log(`🔍 [MARKET_ID_TRACE] Market #1 selected: id="${selected?.id}", platform="${selected?.platform}", title="${selected?.title}"`)
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
                <>
                  {console.log(`🔍 [MARKET_ID_TRACE] VisualizationPanel → AdaptiveChart (Market #1): marketId="${market1.id}", platform="${market1.platform}", title="${market1.title}"`)}
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
                </>
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
                  <Select value={market2ChartType} onValueChange={setMarket2ChartType}>
                    <SelectTrigger className="w-[100px] h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="price">Price</SelectItem>
                      <SelectItem value="orderbook">Orderbook</SelectItem>
                      <SelectItem value="volume">Volume</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Select value={market2?.id || ""} onValueChange={(value) => {
                const selected = subscribedMarkets.find(m => m.id === value)
                console.log(`🔍 [MARKET_ID_TRACE] Market #2 selected: id="${selected?.id}", platform="${selected?.platform}", title="${selected?.title}"`)
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
                <>
                  {console.log(`🔍 [MARKET_ID_TRACE] VisualizationPanel → AdaptiveChart (Market #2): marketId="${market2.id}", platform="${market2.platform}", title="${market2.title}"`)}
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
                </>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Select a market to view chart
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Bottom Row: Large Center Chart */}
        <Card className="h-[600px] w-full">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between gap-4">
              <CardTitle className="text-lg">Pair Comparison</CardTitle>
              <div className="flex items-center gap-2">
                <Tabs value={centerChartType} onValueChange={setCenterChartType}>
                  <TabsList className="grid w-full grid-cols-4">
                    <TabsTrigger value="comparison" className="text-xs">Comparison</TabsTrigger>
                    <TabsTrigger value="price" className="text-xs">Price</TabsTrigger>
                    <TabsTrigger value="volume" className="text-xs">Volume</TabsTrigger>
                    <TabsTrigger value="orderbook" className="text-xs">Orderbook</TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>
            </div>
          </CardHeader>
          <CardContent className="h-[520px] p-4">
            {centerMarkets.length > 0 ? (
              <AdaptiveChart
                  isVisible={true}
                  showControls={true}
                  containerHeight={500}
                  className="comparison-chart w-full h-full"
                  staticData={market1Data}
                  setStaticData={setMarket1Data}
                  chartId="comparison"
                  platform={centerMarkets[0]?.platform}
                  marketId={centerMarkets[0]?.id}
                />
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                Select markets above to compare them here
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Cache Refresh Functionality */}
        <Card className="w-full">
          <CardHeader>
            <CardTitle className="text-lg">Cache Management</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <Button 
                variant="outline" 
                onClick={() => {
                  // Add cache refresh logic here
                  console.log('Refreshing cache...')
                }}
              >
                Refresh Market Cache
              </Button>
              <Button 
                variant="outline"
                onClick={() => {
                  // Add clear cache logic here
                  console.log('Clearing cache...')
                }}
              >
                Clear Cache
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              Use these controls to refresh or clear the market data cache for better performance.
            </p>
          </CardContent>
        </Card>
      </CardContent>
    </Card>
  )
}
