"use client"

import { useState, useEffect } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import { generateOrderbookData } from "@/lib/ChartStuff/mock-data"
import type { Market } from "@/types/market"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface OrderbookChartProps {
  markets: Market[]
}

export function OrderbookChart({ markets }: OrderbookChartProps) {
  const [selectedMarket, setSelectedMarket] = useState<Market | null>(markets[0] || null)
  const [data, setData] = useState<any[]>([])

  useEffect(() => {
    if (selectedMarket) {
      const orderbookData = generateOrderbookData(selectedMarket)
      setData(orderbookData)
    }
  }, [selectedMarket])

  if (markets.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center">No markets selected for visualization</CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium">Orderbook Depth</h3>
        <Select
          value={selectedMarket?.id}
          onValueChange={(value) => {
            const market = markets.find((m) => m.id === value)
            if (market) setSelectedMarket(market)
          }}
        >
          <SelectTrigger className="w-[250px]">
            <SelectValue placeholder="Select market" />
          </SelectTrigger>
          <SelectContent>
            {markets.map((market) => (
              <SelectItem key={market.id} value={market.id}>
                {market.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="h-[400px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{
              top: 5,
              right: 30,
              left: 20,
              bottom: 5,
            }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="price" tickFormatter={(value) => `$${value.toFixed(2)}`} />
            <YAxis />
            <Tooltip
              formatter={(value: number) => [`${value.toFixed(2)}`, "Size"]}
              labelFormatter={(label) => `Price: $${Number.parseFloat(label).toFixed(4)}`}
            />
            <Legend />
            <Bar dataKey="bids" name="Bids" fill="#4ecdc4" />
            <Bar dataKey="asks" name="Asks" fill="#ff6b6b" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
