"use client"

import { Progress } from "@/components/ui/progress"
import { Loader2, Database, Search, CheckCircle2 } from "lucide-react"

interface SearchProgressProps {
  stage: 'initializing' | 'cache_loading' | 'cache_ready' | 'searching' | 'complete'
  message: string
  progress: number
}

export function SearchProgress({ stage, message, progress }: SearchProgressProps) {
  const getIcon = () => {
    switch (stage) {
      case 'initializing':
        return <Loader2 className="h-4 w-4 animate-spin" />
      case 'cache_loading':
        return <Database className="h-4 w-4 animate-pulse" />
      case 'cache_ready':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'searching':
        return <Search className="h-4 w-4 animate-pulse" />
      case 'complete':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      default:
        return <Loader2 className="h-4 w-4 animate-spin" />
    }
  }

  const getProgressColor = () => {
    switch (stage) {
      case 'cache_loading':
        return 'bg-blue-500'
      case 'searching':
        return 'bg-yellow-500'
      case 'complete':
        return 'bg-green-500'
      default:
        return 'bg-primary'
    }
  }

  return (
    <div className="space-y-2 p-3 bg-muted/50 rounded-lg border">
      <div className="flex items-center gap-2">
        {getIcon()}
        <span className="text-sm font-medium">{message}</span>
      </div>
      
      <div className="space-y-1">
        <Progress value={progress} className="h-2" />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span className="capitalize">{stage.replace('_', ' ')}</span>
          <span>{progress}%</span>
        </div>
      </div>
    </div>
  )
}