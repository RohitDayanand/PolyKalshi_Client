/**
 * FULLSCREEN CHART SETTINGS PANEL COMPONENT
 * Contains moving average toggles and other chart settings
 */

import { Card, CardContent } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { SeriesView } from '@/lib/ChartStuff/chart-types'

interface SettingsPanelProps {
  showSettings: boolean
  selectedView: SeriesView
  showCandlestick: boolean
  showYesMA: boolean
  showNoMA: boolean
  onYesMAToggle: (enabled: boolean) => void
  onNoMAToggle: (enabled: boolean) => void
}

export function SettingsPanel({
  showSettings,
  selectedView,
  showCandlestick,
  showYesMA,
  showNoMA,
  onYesMAToggle,
  onNoMAToggle
}: SettingsPanelProps) {
  if (!showSettings) return null

  return (
    <Card className="absolute top-16 right-4 z-10 bg-slate-800 border-slate-700 w-64">
      <CardContent className="p-4">
        <h3 className="text-sm font-medium text-white mb-3">Chart Settings</h3>
        <div className="space-y-3">
          {!showCandlestick && (
            <>
              {(selectedView === 'BOTH' || selectedView === 'YES') && (
                <div className="flex items-center justify-between">
                  <Label htmlFor="yes-ma" className="text-sm text-slate-300">
                    YES Moving Average (20)
                  </Label>
                  <Switch
                    id="yes-ma"
                    checked={showYesMA}
                    onCheckedChange={onYesMAToggle}
                  />
                </div>
              )}
              
              {(selectedView === 'BOTH' || selectedView === 'NO') && (
                <div className="flex items-center justify-between">
                  <Label htmlFor="no-ma" className="text-sm text-slate-300">
                    NO Moving Average (20)
                  </Label>
                  <Switch
                    id="no-ma"
                    checked={showNoMA}
                    onCheckedChange={onNoMAToggle}
                  />
                </div>
              )}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}