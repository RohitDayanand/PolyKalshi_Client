import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

interface LoadingBarProps {
  isLoading: boolean
  className?: string
}

export function LoadingBar({ isLoading, className }: LoadingBarProps) {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    if (isLoading) {
      setProgress(0)
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) return prev
          return prev + Math.random() * 10
        })
      }, 200)

      return () => clearInterval(interval)
    } else {
      setProgress(100)
      setTimeout(() => setProgress(0), 500)
    }
  }, [isLoading])

  if (!isLoading && progress === 0) return null

  return (
    <div 
      className={cn(
        "fixed top-0 left-0 right-0 z-50 h-1 bg-transparent",
        className
      )}
    >
      <div
        className="h-full bg-green-500 transition-all duration-300 ease-out"
        style={{
          width: `${progress}%`,
          boxShadow: '0 0 10px rgba(34, 197, 94, 0.5)'
        }}
      />
    </div>
  )
}