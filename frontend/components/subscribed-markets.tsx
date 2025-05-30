"use client"

import { useMarketContext } from "@/context/market-context"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Trash2, Eye } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"

export function SubscribedMarkets() {
  const { subscribedMarkets, unsubscribeFromMarket, setActiveMarkets } = useMarketContext()

  if (subscribedMarkets.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Subscribed Markets</CardTitle>
        </CardHeader>
        <CardContent className="p-4 text-center text-muted-foreground">
          No subscribed markets. Search and add markets to visualize them.
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Subscribed Markets</CardTitle>
      </CardHeader>
      <CardContent className="p-2">
        <ScrollArea className="h-[300px]">
          <div className="space-y-2 p-2">
            {subscribedMarkets.map((market) => (
              <div key={market.id} className="flex items-start justify-between p-2 rounded-md hover:bg-muted">
                <div className="space-y-1">
                  <div className="font-medium text-sm">{market.title}</div>
                  <div className="flex items-center gap-2">
                    <Badge variant={market.platform === "polymarket" ? "default" : "secondary"} className="text-xs">
                      {market.platform}
                    </Badge>
                  </div>
                </div>
                <div className="flex gap-1">
                  <Button size="icon" variant="ghost" onClick={() => setActiveMarkets([market])}>
                    <Eye className="h-4 w-4" />
                    <span className="sr-only">View</span>
                  </Button>
                  <Button size="icon" variant="ghost" onClick={() => unsubscribeFromMarket(market.id)}>
                    <Trash2 className="h-4 w-4" />
                    <span className="sr-only">Unsubscribe</span>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
