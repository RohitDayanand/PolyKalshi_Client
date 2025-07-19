'use client'

import { useAppSelector } from '@/lib/store/hooks'
import { selectIsLoadingBar } from '@/lib/store/loadingBarSlice'
import { LoadingBar } from '@/components/ui/loading-bar'

export function LoadingBarContainer() {
  const isLoading = useAppSelector(selectIsLoadingBar)

  return <LoadingBar isLoading={isLoading} />
}