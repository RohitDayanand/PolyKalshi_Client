"use client"

import { useState } from "react"
import { useMarketContext } from "@/context/market-context"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { PriceChart } from "@/components/charts/price-chart"
import { OrderbookChart } from "@/components/charts/orderbook-chart"
import { VolumeChart } from "@/components/charts/volume-chart"
import { MarketComparison } from "@/components/charts/market-comparison"
import { Button } from "@/components/ui/button"
import { CheckSquare } from "lucide-react"

export function VisualizationPanel() {
  const { activeMarkets, subscribedMarkets, setActiveMarkets } = useMarketContext()
  const [timeframe, setTimeframe] = useState("24h")
  const [visualizationType, setVisualizationType] = useState("price")

  if (activeMarkets.length === 0) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center h-[600px]">
          <div className="text-center space-y-4">
            <h3 className="text-lg font-medium">No Markets Selected</h3>
            <p className="text-muted-foreground">Subscribe to markets and select them to visualize data</p>
            {subscribedMarkets.length > 0 && (
              <Button onClick={() => setActiveMarkets([subscribedMarkets[0]])}>View Latest Subscription</Button>
            )}
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <CardTitle>Market Visualization</CardTitle>
          <div className="flex items-center gap-2">
            <Select value={timeframe} onValueChange={setTimeframe}>
              <SelectTrigger className="w-[100px]">
                <SelectValue placeholder="Timeframe" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1h">1 Hour</SelectItem>
                <SelectItem value="24h">24 Hours</SelectItem>
                <SelectItem value="7d">7 Days</SelectItem>
                <SelectItem value="30d">30 Days</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={() => setActiveMarkets(subscribedMarkets)}>
              <CheckSquare className="h-4 w-4 mr-2" />
              Select All
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs value={visualizationType} onValueChange={setVisualizationType} className="space-y-4">
          <TabsList>
            <TabsTrigger value="price">Price</TabsTrigger>
            <TabsTrigger value="orderbook">Orderbook</TabsTrigger>
            <TabsTrigger value="volume">Volume</TabsTrigger>
            <TabsTrigger value="comparison">Comparison</TabsTrigger>
          </TabsList>
          <TabsContent value="price" className="space-y-4">
            <PriceChart markets={activeMarkets} timeframe={timeframe} />
          </TabsContent>
          <TabsContent value="orderbook" className="space-y-4">
            <OrderbookChart markets={activeMarkets} />
          </TabsContent>
          <TabsContent value="volume" className="space-y-4">
            <VolumeChart markets={activeMarkets} timeframe={timeframe} />
          </TabsContent>
          <TabsContent value="comparison" className="space-y-4">
            <MarketComparison markets={activeMarkets} timeframe={timeframe} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
