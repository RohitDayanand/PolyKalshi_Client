import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { 
  setSelectedMarket, 
  setSubscription,
  setYesSubscription, 
  setNoSubscription,
  setRangeSubscriptions
} from '../../../lib/store/marketSubscriptionSlice'
import { MarketSubscription, SeriesType, TimeRange } from '../../../lib/chart-types'

export function useMarketSubscriptionState(chartId: string) {
  const selectedMarket = useAppSelector((state) => {
    console.log('📊 Redux State - useMarketSubscriptionState chartId:', chartId)
    console.log('📊 Redux State - Market Subscription instances:', state.marketSubscription.chartInstances)
    const instance = state.marketSubscription.chartInstances[chartId]
    const market = instance?.selectedMarket || {
      yes: { '1H': '', '1W': '', '1M': '', '1Y': '' },
      no: { '1H': '', '1W': '', '1M': '', '1Y': '' }
    }
    console.log('📊 Redux State - Selected Market for chartId', chartId, ':', market)
    return market
  })
  const dispatch = useAppDispatch()

  const setMarket = (market: MarketSubscription) => {
    console.log('🔄 Redux Action - Setting market for chartId', chartId, 'to:', market)
    dispatch(setSelectedMarket({ chartId, market }))
    console.log('✅ Redux Action - Dispatched setSelectedMarket for chartId:', chartId, market)
  }

  // New method: Set subscription for specific series type and range
  const setSubscriptionId = (seriesType: SeriesType, range: TimeRange, subscriptionId: string) => {
    console.log('🔄 Redux Action - Setting subscription for chartId', chartId, ':', { seriesType, range, subscriptionId })
    dispatch(setSubscription({ chartId, seriesType, range, subscriptionId }))
    console.log('✅ Redux Action - Dispatched setSubscription for chartId:', chartId, { seriesType, range, subscriptionId })
  }

  // Updated legacy methods to require range
  const setYesSubscriptionId = (range: TimeRange, subscriptionId: string) => {
    console.log('🔄 Redux Action - Setting YES subscription ID for chartId', chartId, ':', { range, subscriptionId })
    dispatch(setYesSubscription({ chartId, range, subscriptionId }))
    console.log('✅ Redux Action - Dispatched setYesSubscription for chartId:', chartId, { range, subscriptionId })
  }

  const setNoSubscriptionId = (range: TimeRange, subscriptionId: string) => {
    console.log('🔄 Redux Action - Setting NO subscription ID for chartId', chartId, ':', { range, subscriptionId })
    dispatch(setNoSubscription({ chartId, range, subscriptionId }))
    console.log('✅ Redux Action - Dispatched setNoSubscription for chartId:', chartId, { range, subscriptionId })
  }

  // New helper method: Set both YES and NO for a specific range
  const setRangeSubscriptionIds = (range: TimeRange, yesId: string, noId: string) => {
    console.log('🔄 Redux Action - Setting range subscriptions for chartId', chartId, ':', { range, yesId, noId })
    dispatch(setRangeSubscriptions({ chartId, range, yesId, noId }))
    console.log('✅ Redux Action - Dispatched setRangeSubscriptions for chartId:', chartId, { range, yesId, noId })
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

  console.log('🎣 useMarketSubscriptionState hook - chartId:', chartId, 'selectedMarket:', selectedMarket)

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
