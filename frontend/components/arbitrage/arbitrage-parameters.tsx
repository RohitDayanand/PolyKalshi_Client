"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Settings, Save, RotateCcw } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

interface ArbitrageParameters {
  min_spread_threshold: number
  alert_deduplication_threshold: number
  max_alerts_per_minute: number
  enable_notifications: boolean
  market_pair_filters: string[]
  confidence_threshold: number
}

interface ArbitrageParametersProps {
  className?: string
  onParametersChange?: (params: ArbitrageParameters) => void
}

const DEFAULT_PARAMETERS: ArbitrageParameters = {
  min_spread_threshold: 0.02, // 2%
  alert_deduplication_threshold: 0.10, // 10%
  max_alerts_per_minute: 10,
  enable_notifications: true,
  market_pair_filters: [],
  confidence_threshold: 0.8
}

export function ArbitrageParameters({ className, onParametersChange }: ArbitrageParametersProps) {
  const [parameters, setParameters] = useState<ArbitrageParameters>(DEFAULT_PARAMETERS)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const { toast } = useToast()

  const updateParameter = <K extends keyof ArbitrageParameters>(
    key: K,
    value: ArbitrageParameters[K]
  ) => {
    setParameters(prev => ({ ...prev, [key]: value }))
    setHasUnsavedChanges(true)
  }

  const handleSpreadThresholdChange = (value: number[]) => {
    updateParameter('min_spread_threshold', value[0] / 100) // Convert percentage to decimal
  }

  const handleDeduplicationThresholdChange = (value: number[]) => {
    updateParameter('alert_deduplication_threshold', value[0] / 100)
  }

  const handleConfidenceThresholdChange = (value: number[]) => {
    updateParameter('confidence_threshold', value[0] / 100)
  }

  const handleMaxAlertsChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(event.target.value)
    if (!isNaN(value) && value >= 1 && value <= 100) {
      updateParameter('max_alerts_per_minute', value)
    }
  }

  const saveParameters = async () => {
    try {
      // TODO: Implement API call to backend
      // await fetch('/api/arbitrage/parameters', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(parameters)
      // })
      
      onParametersChange?.(parameters)
      setHasUnsavedChanges(false)
      
      toast({
        title: "Parameters saved",
        description: "Arbitrage parameters have been updated successfully.",
      })
    } catch (error) {
      toast({
        title: "Error saving parameters",
        description: "Failed to update arbitrage parameters. Please try again.",
        variant: "destructive",
      })
    }
  }

  const resetToDefaults = () => {
    setParameters(DEFAULT_PARAMETERS)
    setHasUnsavedChanges(true)
    toast({
      title: "Reset to defaults",
      description: "Parameters have been reset to default values.",
    })
  }

  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(1)}%`
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            <CardTitle className="text-lg">Arbitrage Parameters</CardTitle>
          </div>
          {hasUnsavedChanges && (
            <Badge variant="outline" className="text-orange-600 border-orange-600">
              Unsaved changes
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Spread Threshold */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label htmlFor="spread-threshold" className="text-sm font-medium">
              Minimum Spread Threshold
            </Label>
            <span className="text-sm text-muted-foreground">
              {formatPercentage(parameters.min_spread_threshold)}
            </span>
          </div>
          <Slider
            id="spread-threshold"
            min={5} // 0.5%
            max={100} // 10%
            step={5}
            value={[parameters.min_spread_threshold * 100]}
            onValueChange={handleSpreadThresholdChange}
            className="w-full"
          />
          <p className="text-xs text-muted-foreground">
            Minimum profit spread required to trigger an alert
          </p>
        </div>

        <Separator />

        {/* Deduplication Threshold */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label htmlFor="dedup-threshold" className="text-sm font-medium">
              Alert Deduplication Threshold
            </Label>
            <span className="text-sm text-muted-foreground">
              {formatPercentage(parameters.alert_deduplication_threshold)}
            </span>
          </div>
          <Slider
            id="dedup-threshold"
            min={50} // 5%
            max={500} // 50%
            step={25}
            value={[parameters.alert_deduplication_threshold * 100]}
            onValueChange={handleDeduplicationThresholdChange}
            className="w-full"
          />
          <p className="text-xs text-muted-foreground">
            Only re-alert if spread changes by more than this amount
          </p>
        </div>

        <Separator />

        {/* Confidence Threshold */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label htmlFor="confidence-threshold" className="text-sm font-medium">
              Confidence Threshold
            </Label>
            <span className="text-sm text-muted-foreground">
              {formatPercentage(parameters.confidence_threshold)}
            </span>
          </div>
          <Slider
            id="confidence-threshold"
            min={50} // 50%
            max={100} // 100%
            step={5}
            value={[parameters.confidence_threshold * 100]}
            onValueChange={handleConfidenceThresholdChange}
            className="w-full"
          />
          <p className="text-xs text-muted-foreground">
            Minimum confidence score required for alerts
          </p>
        </div>

        <Separator />

        {/* Max Alerts per Minute */}
        <div className="space-y-3">
          <Label htmlFor="max-alerts" className="text-sm font-medium">
            Max Alerts per Minute
          </Label>
          <Input
            id="max-alerts"
            type="number"
            min="1"
            max="100"
            value={parameters.max_alerts_per_minute}
            onChange={handleMaxAlertsChange}
            className="w-full"
          />
          <p className="text-xs text-muted-foreground">
            Rate limit for alert notifications (1-100)
          </p>
        </div>

        <Separator />

        {/* Enable Notifications */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <Label htmlFor="notifications" className="text-sm font-medium">
              Enable Notifications
            </Label>
            <p className="text-xs text-muted-foreground">
              Receive browser notifications for new alerts
            </p>
          </div>
          <Switch
            id="notifications"
            checked={parameters.enable_notifications}
            onCheckedChange={(checked) => updateParameter('enable_notifications', checked)}
          />
        </div>

        <Separator />

        {/* Action Buttons */}
        <div className="flex items-center gap-2 pt-2">
          <Button
            onClick={saveParameters}
            disabled={!hasUnsavedChanges}
            className="flex-1"
          >
            <Save className="h-4 w-4 mr-2" />
            Save Parameters
          </Button>
          <Button
            variant="outline"
            onClick={resetToDefaults}
            size="sm"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>

        {/* Current Configuration Summary */}
        <div className="mt-4 p-3 bg-muted/50 rounded-lg">
          <h4 className="text-sm font-medium mb-2">Current Configuration</h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>Min Spread: {formatPercentage(parameters.min_spread_threshold)}</div>
            <div>Max Alerts/min: {parameters.max_alerts_per_minute}</div>
            <div>Dedup: {formatPercentage(parameters.alert_deduplication_threshold)}</div>
            <div>Confidence: {formatPercentage(parameters.confidence_threshold)}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}