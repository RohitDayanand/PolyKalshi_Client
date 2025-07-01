"use client"

import { Provider } from 'react-redux'
import { store } from '@/lib/store/index'
import { type ReactNode } from 'react'

export function ReduxProvider({ children }: { children: ReactNode }) {
  return <Provider store={store}>{children}</Provider>
}
