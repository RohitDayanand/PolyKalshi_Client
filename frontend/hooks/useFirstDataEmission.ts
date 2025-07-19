import { useEffect } from 'react'
import { useAppDispatch } from '@/lib/store/hooks'
import { stopLoading } from '@/lib/store/loadingBarSlice'
import { rxjsChannelManager } from '@/lib/RxJSChannel'

export function useFirstDataEmission() {
  const dispatch = useAppDispatch()

  useEffect(() => {
    const subscription = rxjsChannelManager.getFirstDataObservable().subscribe({
      next: (message) => {
        console.log('🎯 First data emission received:', message)
        dispatch(stopLoading())
      },
      error: (error) => {
        console.error('❌ Error in first data emission:', error)
        dispatch(stopLoading())
      }
    })

    return () => subscription.unsubscribe()
  }, [dispatch])
}