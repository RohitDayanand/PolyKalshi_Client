"use client"

import { useState, useEffect } from "react"
import { Card, CardContent } from "@/components/ui/card"
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ZAxis,
} from "recharts"
import { generateComparisonData } from "@/lib/mock-data"
import type { Market } from "@/types/market"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface MarketComparisonProps {
  markets: Market[]
  timeframe: string
}

export function MarketComparison({ markets, timeframe }: MarketComparisonProps) {
  const [metric1, setMetric1] = useState("price")
  const [metric2, setMetric2] = useState("volume")
  const [data, setData] = useState<any[]>([])

  useEffect(() => {
    const comparisonData = generateComparisonData(markets, timeframe, metric1, metric2)
    setData(comparisonData)
  }, [markets, timeframe, metric1, metric2])

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

  const metricOptions = [
    { value: "price", label: "Price" },
    { value: "volume", label: "Volume" },
    { value: "liquidity", label: "Liquidity" },
    { value: "volatility", label: "Volatility" },
  ]

  const formatMetricValue = (value: number, metric: string) => {
    switch (metric) {
      case "price":
        return `$${value.toFixed(4)}`
      case "volume":
        return `$${value.toLocaleString()}`
      case "liquidity":
        return `$${value.toLocaleString()}`
      case "volatility":
        return `${(value * 100).toFixed(2)}%`
      default:
        return value.toString()
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h3 className="text-lg font-medium">Market Comparison</h3>
        <div className="flex flex-col sm:flex-row gap-2">
          <Select value={metric1} onValueChange={setMetric1}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="X Axis" />
            </SelectTrigger>
            <SelectContent>
              {metricOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={metric2} onValueChange={setMetric2}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Y Axis" />
            </SelectTrigger>
            <SelectContent>
              {metricOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="h-[400px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart
            margin={{
              top: 20,
              right: 20,
              bottom: 20,
              left: 20,
            }}
          >
            <CartesianGrid />
            <XAxis
              type="number"
              dataKey={metric1}
              name={metric1.charAt(0).toUpperCase() + metric1.slice(1)}
              tickFormatter={(value) => formatMetricValue(value, metric1)}
            />
            <YAxis
              type="number"
              dataKey={metric2}
              name={metric2.charAt(0).toUpperCase() + metric2.slice(1)}
              tickFormatter={(value) => formatMetricValue(value, metric2)}
            />
            <ZAxis range={[60, 400]} />
            <Tooltip
              formatter={(value: number, name: string) => {
                if (name === metric1) {
                  return [formatMetricValue(value, metric1), metric1.charAt(0).toUpperCase() + metric1.slice(1)]
                }
                return [formatMetricValue(value, metric2), metric2.charAt(0).toUpperCase() + metric2.slice(1)]
              }}
              itemSorter={(item) => -item.value}
            />
            <Legend />
            {markets.map((market, index) => (
              <Scatter
                key={market.id}
                name={market.title}
                data={data.filter((item) => item.marketId === market.id)}
                fill={getColor(index)}
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
