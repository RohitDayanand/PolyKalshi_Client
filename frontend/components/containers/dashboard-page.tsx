"use client"

import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { MarketList } from "@/components/containers/market-list"
import { VisualizationPanel } from "@/components/containers/visualization-panel"
import { SubscribedMarkets } from "@/components/containers/subscribed-markets"
import { CacheDebugPanel } from "@/components/containers/cache-debug-panel"
import { QuickKalshiSubscribe } from "@/components/containers/quick-kalshi-subscribe"

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("polymarket")

  return (
    <div className="flex flex-col min-h-screen">
      <header className="border-b">
        <div className="container flex items-center justify-between py-4">
          <h1 className="text-2xl font-bold">Market Analysis Dashboard</h1>
        </div>
      </header>
      <main className="flex-1 container py-6 max-w-full">
        {/* Full-width Visualization Panel */}
        <div className="mb-8">
          <VisualizationPanel />
        </div>
        
        {/* Below: Sidebar content in a responsive grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-6">
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid grid-cols-2 w-full">
                <TabsTrigger value="polymarket">Polymarket</TabsTrigger>
                <TabsTrigger value="kalshi">Kalshi</TabsTrigger>
              </TabsList>
              <TabsContent value="polymarket" className="space-y-4 mt-4">
                <MarketList platform="polymarket" />
              </TabsContent>
              <TabsContent value="kalshi" className="space-y-4 mt-4">
                <MarketList platform="kalshi" />
              </TabsContent>
            </Tabs>
            <SubscribedMarkets />
          </div>
          <div>
            <CacheDebugPanel />
          </div>
          <div className="space-y-6">
            <QuickKalshiSubscribe />
          </div>
        </div>
      </main>
    </div>
  )
}
