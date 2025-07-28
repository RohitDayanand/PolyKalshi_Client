"use client"

import { useState, useCallback, useRef } from 'react'
import type { Market } from '@/types/market'

interface SearchProgress {
  stage: 'initializing' | 'cache_loading' | 'cache_ready' | 'searching' | 'complete'
  message: string
  progress: number
}

interface SearchState {
  isLoading: boolean
  progress: SearchProgress | null
  results: Market[]
  error: string | null
}

interface SearchResponse {
  success: boolean
  data: Market[]
  platform: string
  query: string
  timestamp: string
  cache: {
    marketCount: number
    lastUpdate: string
    isStale: boolean
  }
}

export function useStreamingSearch() {
  const [searchState, setSearchState] = useState<SearchState>({
    isLoading: false,
    progress: null,
    results: [],
    error: null
  })
  
  const eventSourceRef = useRef<EventSource | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const search = useCallback(async (platform: 'polymarket' | 'kalshi', query: string) => {
    // Cancel any ongoing search
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    // Reset state
    setSearchState({
      isLoading: true,
      progress: null,
      results: [],
      error: null
    })

    abortControllerRef.current = new AbortController()

    try {
      const url = `/api/search/stream?platform=${platform}&query=${encodeURIComponent(query)}`
      
      // Create EventSource for streaming
      const eventSource = new EventSource(url)
      eventSourceRef.current = eventSource

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          switch (data.type) {
            case 'progress':
              setSearchState(prev => ({
                ...prev,
                progress: data.data
              }))
              break
              
            case 'results':
              const response: SearchResponse = data.data
              setSearchState(prev => ({
                ...prev,
                isLoading: false,
                results: response.data,
                progress: {
                  stage: 'complete',
                  message: `Found ${response.data.length} markets`,
                  progress: 100
                }
              }))
              eventSource.close()
              eventSourceRef.current = null
              break
              
            case 'error':
              setSearchState(prev => ({
                ...prev,
                isLoading: false,
                error: data.data.message,
                progress: null
              }))
              eventSource.close()
              eventSourceRef.current = null
              break
          }
        } catch (parseError) {
          console.error('Failed to parse SSE data:', parseError)
        }
      }

      eventSource.onerror = (error) => {
        console.error('EventSource error:', error)
        setSearchState(prev => ({
          ...prev,
          isLoading: false,
          error: 'Connection error occurred',
          progress: null
        }))
        eventSource.close()
        eventSourceRef.current = null
      }

    } catch (error) {
      setSearchState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Search failed',
        progress: null
      }))
    }
  }, [])

  const cancelSearch = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    setSearchState(prev => ({
      ...prev,
      isLoading: false,
      progress: null
    }))
  }, [])

  return {
    search,
    cancelSearch,
    isLoading: searchState.isLoading,
    progress: searchState.progress,
    results: searchState.results,
    error: searchState.error
  }
}