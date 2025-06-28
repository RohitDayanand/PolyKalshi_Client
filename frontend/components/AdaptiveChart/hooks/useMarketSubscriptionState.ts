import { useAppSelector, useAppDispatch } from '../../../lib/store/hooks'
import { 
  setSelectedMarket, 
  setSubscription,
  setYesSubscription, 
  setNoSubscription,
  setRangeSubscriptions
} from '../../../lib/store/marketSubscriptionSlice'
import { MarketSubscription, SeriesType, TimeRange } from '../../../lib/ChartStuff/chart-types'

export function useMarketSubscriptionState(chartId: string) {
  const selectedMarket = useAppSelector((state) => {
    const instance = state.marketSubscription.chartInstances[chartId]
    const market = instance?.selectedMarket || {
      yes: { '1H': '', '1W': '', '1M': '', '1Y': '' },
      no: { '1H': '', '1W': '', '1M': '', '1Y': '' }
    }
    return market
  })
  const dispatch = useAppDispatch()

  const setMarket = (market: MarketSubscription) => {
    dispatch(setSelectedMarket({ chartId, market }))
  }

  // New method: Set subscription for specific series type and range
  const setSubscriptionId = (seriesType: SeriesType, range: TimeRange, subscriptionId: string) => {
    dispatch(setSubscription({ chartId, seriesType, range, subscriptionId }))
  }

  // Updated legacy methods to require range
  const setYesSubscriptionId = (range: TimeRange, subscriptionId: string) => {
    dispatch(setYesSubscription({ chartId, range, subscriptionId }))
  }

  const setNoSubscriptionId = (range: TimeRange, subscriptionId: string) => {
    dispatch(setNoSubscription({ chartId, range, subscriptionId }))
  }

  // New helper method: Set both YES and NO for a specific range
  const setRangeSubscriptionIds = (range: TimeRange, yesId: string, noId: string) => {
    dispatch(setRangeSubscriptions({ chartId, range, yesId, noId }))
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
