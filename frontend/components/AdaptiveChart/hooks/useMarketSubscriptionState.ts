import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { 
  setSelectedMarket, 
  setSubscription,
  setYesSubscription, 
  setNoSubscription,
  setRangeSubscriptions 
} from '../../../lib/store/marketSubscriptionSlice'
import { MarketSubscription, SeriesType, TimeRange } from '../../../lib/chart-types'

export function useMarketSubscriptionState() {
  const selectedMarket = useAppSelector((state) => {
    console.log('📊 Redux State - Full State:', state)
    console.log('📊 Redux State - Market Subscription:', state.marketSubscription)
    console.log('📊 Redux State - Selected Market:', state.marketSubscription.selectedMarket)
    return state.marketSubscription.selectedMarket
  })
  const dispatch = useAppDispatch()

  const setMarket = (market: MarketSubscription) => {
    console.log('🔄 Redux Action - Setting market to:', market)
    dispatch(setSelectedMarket(market))
    console.log('✅ Redux Action - Dispatched setSelectedMarket:', market)
  }

  // New method: Set subscription for specific series type and range
  const setSubscriptionId = (seriesType: SeriesType, range: TimeRange, subscriptionId: string) => {
    console.log('🔄 Redux Action - Setting subscription:', { seriesType, range, subscriptionId })
    dispatch(setSubscription({ seriesType, range, subscriptionId }))
    console.log('✅ Redux Action - Dispatched setSubscription:', { seriesType, range, subscriptionId })
  }

  // Updated legacy methods to require range
  const setYesSubscriptionId = (range: TimeRange, subscriptionId: string) => {
    console.log('🔄 Redux Action - Setting YES subscription ID:', { range, subscriptionId })
    dispatch(setYesSubscription({ range, subscriptionId }))
    console.log('✅ Redux Action - Dispatched setYesSubscription:', { range, subscriptionId })
  }

  const setNoSubscriptionId = (range: TimeRange, subscriptionId: string) => {
    console.log('🔄 Redux Action - Setting NO subscription ID:', { range, subscriptionId })
    dispatch(setNoSubscription({ range, subscriptionId }))
    console.log('✅ Redux Action - Dispatched setNoSubscription:', { range, subscriptionId })
  }

  // New helper method: Set both YES and NO for a specific range
  const setRangeSubscriptionIds = (range: TimeRange, yesId: string, noId: string) => {
    console.log('🔄 Redux Action - Setting range subscriptions:', { range, yesId, noId })
    dispatch(setRangeSubscriptions({ range, yesId, noId }))
    console.log('✅ Redux Action - Dispatched setRangeSubscriptions:', { range, yesId, noId })
  }

  // Helper selector: Get subscription ID for specific series type and range
  const getSubscriptionId = (seriesType: SeriesType, range: TimeRange): string => {
    return seriesType === 'YES' ? selectedMarket.yes[range] : selectedMarket.no[range]
  }

  // Helper selector: Get all subscriptions for a specific range
  const getRangeSubscriptions = (range: TimeRange) => {
    return {
      yes: selectedMarket.yes[range],
      no: selectedMarket.no[range]
    }
  }

  console.log('🎣 useMarketSubscriptionState hook - Current selectedMarket:', selectedMarket)

  return {
    selectedMarket,
    setMarket,
    setSubscriptionId,
    setYesSubscriptionId,
    setNoSubscriptionId,
    setRangeSubscriptionIds,
    getSubscriptionId,
    getRangeSubscriptions
  }
}
