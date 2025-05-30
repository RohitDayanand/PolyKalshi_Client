"use client"

import { useState, useEffect } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import { generateMarketPriceData } from "@/lib/mock-data"
import type { Market } from "@/types/market"
import { Badge } from "@/components/ui/badge"

interface PriceChartProps {
  markets: Market[]
  timeframe: string
}

export function PriceChart({ markets, timeframe }: PriceChartProps) {
  const [data, setData] = useState<any[]>([])

  useEffect(() => {
    // Generate mock data for each market
    const combinedData = generateMarketPriceData(markets, timeframe)
    setData(combinedData)
  }, [markets, timeframe])

  if (markets.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center">No markets selected for visualization</CardContent>
      </Card>
    )
  }

  // Generate a unique color for each market
  const getColor = (index: number) => {
    const colors = ["#ff6b6b", "#4ecdc4", "#1a535c", "#ff9f1c", "#7b68ee", "#2ec4b6"]
    return colors[index % colors.length]
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {markets.map((market, index) => (
          <Badge key={market.id} style={{ backgroundColor: getColor(index) }}>
            {market.title}
          </Badge>
        ))}
      </div>
      <div className="h-[400px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{
              top: 5,
              right: 30,
              left: 20,
              bottom: 5,
            }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis domain={[0, 1]} tickFormatter={(value) => `$${value.toFixed(2)}`} />
            <Tooltip
              formatter={(value: number) => [`$${value.toFixed(4)}`, "Price"]}
              labelFormatter={(label) => `Time: ${label}`}
            />
            <Legend />
            {markets.map((market, index) => (
              <Line
                key={market.id}
                type="monotone"
                dataKey={market.id}
                name={market.title}
                stroke={getColor(index)}
                activeDot={{ r: 8 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
