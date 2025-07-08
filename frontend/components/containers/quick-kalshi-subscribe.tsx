"use client"

import { useDispatch, useSelector } from "react-redux"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { callSubscriptionAPI, selectIsLoading } from "@/lib/store/apiSubscriptionSlice"

export function QuickKalshiSubscribe() {
  const dispatch = useDispatch()
  const isLoading = useSelector(selectIsLoading)

  const handleSubscribeKalshi = () => {
    const market = {
      id: 'KXUSAIRANAGREEMENT-26',
      title: 'KXUSAIRANAGREEMENT-26',
      kalshiTicker: 'KXUSAIRANAGREEMENT-26',
      platform: 'kalshi' as const
    }

    console.log('🚀 Quick subscribing to Kalshi market:', market)
    
    dispatch(callSubscriptionAPI({ 
      platform: 'kalshi', 
      market 
    }))
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>Quick Kalshi Subscribe</CardTitle>
      </CardHeader>
      <CardContent>
        <Button 
          onClick={handleSubscribeKalshi}
          disabled={isLoading}
          className="w-full"
        >
          {isLoading ? 'Subscribing...' : 'Subscribe to KXUSAIRANAGREEMENT-26'}
        </Button>
      </CardContent>
    </Card>
  )
}