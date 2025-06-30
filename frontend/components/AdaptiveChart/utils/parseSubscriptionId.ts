// Utility to parse a subscription ID in the format "marketId&side&timeRange"
export function parseSubscriptionId(subscriptionId: string): { marketId: string, side: 'yes' | 'no', timeRange: string } | null {
  const subscriptionParts = subscriptionId.split('&')
  if (subscriptionParts.length >= 3) {
    const [marketId, sideStr, timeRange] = subscriptionParts
    const side = sideStr.toLowerCase() as 'yes' | 'no'
    return { marketId, side, timeRange }
  }
  return null
}