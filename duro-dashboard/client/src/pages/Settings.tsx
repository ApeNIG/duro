import { useState } from 'react'
import { Settings as SettingsIcon, Database, FolderOpen, Shield, Palette } from 'lucide-react'
import { useHealth } from '@/hooks/useStats'

interface SettingCardProps {
  icon: React.ReactNode
  title: string
  description: string
  children: React.ReactNode
}

function SettingCard({ icon, title, description, children }: SettingCardProps) {
  return (
    <div className="bg-card border border-border rounded-lg p-5">
      <div className="flex items-start gap-4">
        <div className="p-2 rounded bg-accent-dim text-accent">
          {icon}
        </div>
        <div className="flex-1">
          <h3 className="font-medium text-text-primary mb-1">{title}</h3>
          <p className="text-sm text-text-secondary mb-4">{description}</p>
          {children}
        </div>
      </div>
    </div>
  )
}

export default function Settings() {
  const { data: health } = useHealth()
  const [hideLogs, setHideLogs] = useState(true)
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [pollInterval, setPollInterval] = useState(5)

  return (
    <div className="h-full overflow-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <SettingsIcon className="w-5 h-5 text-accent" />
        <h1 className="text-xl font-display font-semibold">Settings</h1>
      </div>

      <div className="max-w-3xl space-y-6">
        {/* Database Status */}
        <SettingCard
          icon={<Database className="w-4 h-4" />}
          title="Database"
          description="Connection status and statistics"
        >
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex justify-between p-3 bg-page rounded">
              <span className="text-text-secondary">Status</span>
              <span className={health?.database === 'connected' ? 'text-accent' : 'text-error'}>
                {health?.database || 'unknown'}
              </span>
            </div>
            <div className="flex justify-between p-3 bg-page rounded">
              <span className="text-text-secondary">Artifacts</span>
              <span className="text-text-primary font-mono">
                {health?.artifact_count?.toLocaleString() || '-'}
              </span>
            </div>
            <div className="flex justify-between p-3 bg-page rounded">
              <span className="text-text-secondary">Latency</span>
              <span className="text-text-primary font-mono">
                {health?.latency_ms ? `${health.latency_ms.toFixed(1)}ms` : '-'}
              </span>
            </div>
            <div className="flex justify-between p-3 bg-page rounded">
              <span className="text-text-secondary">Path</span>
              <span className="text-text-primary font-mono text-xs truncate">
                ~/.agent/memory/index.db
              </span>
            </div>
          </div>
        </SettingCard>

        {/* Display Preferences */}
        <SettingCard
          icon={<Palette className="w-4 h-4" />}
          title="Display"
          description="Customize how data is displayed"
        >
          <div className="space-y-4">
            <label className="flex items-center justify-between p-3 bg-page rounded cursor-pointer">
              <div>
                <div className="text-sm text-text-primary">Hide logs by default</div>
                <div className="text-xs text-text-secondary">Logs make up ~55% of artifacts</div>
              </div>
              <input
                type="checkbox"
                checked={hideLogs}
                onChange={(e) => setHideLogs(e.target.checked)}
                className="w-5 h-5 rounded border-border bg-card accent-accent"
              />
            </label>

            <div className="p-3 bg-page rounded">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-text-primary">Theme</div>
                <span className="text-xs text-text-secondary">(coming soon)</span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setTheme('dark')}
                  className={`flex-1 py-2 px-3 rounded text-sm transition-colors ${
                    theme === 'dark'
                      ? 'bg-accent text-page'
                      : 'bg-card border border-border text-text-secondary'
                  }`}
                >
                  Dark
                </button>
                <button
                  onClick={() => setTheme('light')}
                  disabled
                  className="flex-1 py-2 px-3 rounded text-sm bg-card border border-border text-text-secondary/50 cursor-not-allowed"
                >
                  Light
                </button>
              </div>
            </div>
          </div>
        </SettingCard>

        {/* Polling Settings */}
        <SettingCard
          icon={<Shield className="w-4 h-4" />}
          title="Real-time Updates"
          description="Configure how often data refreshes"
        >
          <div className="p-3 bg-page rounded">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm text-text-primary">Heartbeat interval</div>
              <span className="text-xs text-text-secondary font-mono">{pollInterval}s</span>
            </div>
            <input
              type="range"
              min={1}
              max={30}
              value={pollInterval}
              onChange={(e) => setPollInterval(Number(e.target.value))}
              className="w-full accent-accent"
            />
            <div className="flex justify-between text-xs text-text-secondary mt-1">
              <span>1s (fast)</span>
              <span>30s (slow)</span>
            </div>
          </div>
        </SettingCard>

        {/* Workspace */}
        <SettingCard
          icon={<FolderOpen className="w-4 h-4" />}
          title="Workspace"
          description="Allowed directories and paths"
        >
          <div className="space-y-2 text-sm">
            <div className="p-3 bg-page rounded font-mono text-xs text-text-secondary">
              ~/.agent/
            </div>
            <div className="p-3 bg-page rounded font-mono text-xs text-text-secondary">
              ~/duro-mcp/
            </div>
            <p className="text-xs text-text-secondary mt-2">
              Workspace paths are configured in Duro MCP settings
            </p>
          </div>
        </SettingCard>

        {/* Version Info */}
        <div className="text-center text-xs text-text-secondary py-4">
          Duro Dashboard v1.0.0 | FastAPI Backend | React + Tailwind
        </div>
      </div>
    </div>
  )
}
