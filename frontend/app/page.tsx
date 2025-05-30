import type { Metadata } from "next"
import DashboardPage from "@/components/dashboard-page"

export const metadata: Metadata = {
  title: "Market Analysis Dashboard",
  description: "Search, compare, and analyze prediction markets from Polymarket and Kalshi",
}

export default function Home() {
  return <DashboardPage />
}
