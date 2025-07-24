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
  min_trade_size: number
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
  min_trade_size: 10.0, // $10
  alert_deduplication_threshold: 0.10, // 10%
  max_alerts_per_minute: 10,
  enable_notifications: true,
  market_pair_filters: [],
  confidence_threshold: 0.8
}

export function ArbitrageParameters({ className, onParametersChange }: ArbitrageParametersProps) {
  const [parameters, setParameters] = useState<ArbitrageParameters>(DEFAULT_PARAMETERS)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
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

  const handleTradeSizeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(event.target.value)
    if (!isNaN(value) && value >= 1 && value <= 10000) {
      updateParameter('min_trade_size', value)
    }
  }

  const validateParameters = () => {
    const errors: string[] = [];
    
    if (parameters.min_spread_threshold < 0 || parameters.min_spread_threshold > 1) {
      errors.push("Spread threshold must be between 0% and 100%");
    }
    
    if (parameters.min_trade_size < 1 || parameters.min_trade_size > 10000) {
      errors.push("Trade size must be between $1 and $10,000");
    }
    
    return errors;
  };

  const saveParameters = async () => {
    if (isSaving) return;
    
    // Validate parameters before sending
    const validationErrors = validateParameters();
    if (validationErrors.length > 0) {
      toast({
        title: "Validation Error",
        description: validationErrors.join(". "),
        variant: "destructive",
      });
      return;
    }
    
    setIsSaving(true);
    try {
      // Prepare payload with only backend-relevant parameters
      const payload = {
        min_spread_threshold: parameters.min_spread_threshold,
        min_trade_size: parameters.min_trade_size,
        source: "frontend"
      };

      const response = await fetch('/api/arbitrage/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      if (result.success) {
        onParametersChange?.(parameters);
        setHasUnsavedChanges(false);
        
        toast({
          title: "Parameters saved",
          description: "Arbitrage parameters have been updated successfully.",
        });
      } else {
        // Handle backend validation errors
        if (result.errors && Array.isArray(result.errors)) {
          throw new Error(result.errors.join(". "));
        } else {
          throw new Error(result.message || "Failed to update parameters");
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Unknown error occurred";
      console.error("Failed to save arbitrage parameters:", error);
      
      toast({
        title: "Error saving parameters",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
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

        {/* Minimum Trade Size */}
        <div className="space-y-3">
          <Label htmlFor="trade-size" className="text-sm font-medium">
            Minimum Trade Size ($)
          </Label>
          <Input
            id="trade-size"
            type="number"
            min="1"
            max="10000"
            step="0.1"
            value={parameters.min_trade_size}
            onChange={handleTradeSizeChange}
            className="w-full"
          />
          <p className="text-xs text-muted-foreground">
            Minimum trade size required to trigger arbitrage alerts ($1-$10,000)
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
            disabled={!hasUnsavedChanges || isSaving}
            className="flex-1"
          >
            <Save className="h-4 w-4 mr-2" />
            {isSaving ? "Saving..." : "Save Parameters"}
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
            <div>Min Trade Size: ${parameters.min_trade_size}</div>
            <div>Max Alerts/min: {parameters.max_alerts_per_minute}</div>
            <div>Dedup: {formatPercentage(parameters.alert_deduplication_threshold)}</div>
            <div>Confidence: {formatPercentage(parameters.confidence_threshold)}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}