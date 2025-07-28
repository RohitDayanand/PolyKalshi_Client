"use client"

import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { MarketList } from "@/components/containers/market-list"
import { VisualizationPanel } from "@/components/containers/visualization-panel"
import { SubscribedMarkets } from "@/components/containers/subscribed-markets"
import { ArbitrageAlerts, ArbitrageParameters } from "@/components/arbitrage"
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable"

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("polymarket")
  
  // Panel layout state with localStorage persistence
  const [panelSizes, setPanelSizes] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('arbitrage-panel-sizes')
      return saved ? JSON.parse(saved) : [75, 25] // Default: 75% alerts, 25% parameters
    }
    return [75, 25]
  })

  const handlePanelResize = (sizes: number[]) => {
    setPanelSizes(sizes)
    if (typeof window !== 'undefined') {
      localStorage.setItem('arbitrage-panel-sizes', JSON.stringify(sizes))
    }
  }

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

        {/* Arbitrage Dashboard Section */}
        <div className="mb-8">
          <div className="h-[600px] hidden lg:block">
            <ResizablePanelGroup 
              direction="horizontal" 
              onLayout={handlePanelResize}
              className="rounded-lg border"
            >
              <ResizablePanel 
                defaultSize={panelSizes[0]} 
                minSize={20}
                className="p-2"
              >
                <ArbitrageAlerts className="h-full" />
              </ResizablePanel>
              <ResizableHandle withHandle />
              <ResizablePanel 
                defaultSize={panelSizes[1]} 
                minSize={20}
                className="p-2"
              >
                <ArbitrageParameters className="h-full" />
              </ResizablePanel>
            </ResizablePanelGroup>
          </div>
          
          {/* Mobile fallback - stack vertically */}
          <div className="lg:hidden space-y-6">
            <ArbitrageAlerts />
            <ArbitrageParameters />
          </div>
        </div>
        
        {/* Below: Sidebar content in a responsive grid */}
        <div className="grid grid-cols-1 gap-6">
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
        </div>
      </main>
    </div>
  )
}
