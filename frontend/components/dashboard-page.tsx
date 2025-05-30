"use client"

import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { MarketList } from "@/components/market-list"
import { VisualizationPanel } from "@/components/visualization-panel"
import { SubscribedMarkets } from "@/components/subscribed-markets"
import { CacheDebugPanel } from "@/components/cache-debug-panel"
import { MarketProvider } from "@/context/market-context"

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("polymarket")

  return (
    <MarketProvider>
      <div className="flex flex-col min-h-screen">
        <header className="border-b">
          <div className="container flex items-center justify-between py-4">
            <h1 className="text-2xl font-bold">Market Analysis Dashboard</h1>
          </div>
        </header>
        <main className="flex-1 container py-6">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            <div className="md:col-span-3 space-y-6">
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
            <div className="md:col-span-6">
              <VisualizationPanel />
            </div>
            <div className="md:col-span-3">
              <CacheDebugPanel />
            </div>
          </div>
        </main>
      </div>
    </MarketProvider>
  )
}
