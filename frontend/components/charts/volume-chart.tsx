"use client"

import { useState, useEffect } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import { generateVolumeData } from "@/lib/mock-data"
import type { Market } from "@/types/market"
import { Badge } from "@/components/ui/badge"

interface VolumeChartProps {
  markets: Market[]
  timeframe: string
}

export function VolumeChart({ markets, timeframe }: VolumeChartProps) {
  const [data, setData] = useState<any[]>([])

  useEffect(() => {
    const volumeData = generateVolumeData(markets, timeframe)
    setData(volumeData)
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
            <XAxis dataKey="time" />
            <YAxis tickFormatter={(value) => `$${value.toLocaleString()}`} />
            <Tooltip
              formatter={(value: number) => [`$${value.toLocaleString()}`, "Volume"]}
              labelFormatter={(label) => `Time: ${label}`}
            />
            <Legend />
            {markets.map((market, index) => (
              <Bar key={market.id} dataKey={market.id} name={market.title} fill={getColor(index)} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
