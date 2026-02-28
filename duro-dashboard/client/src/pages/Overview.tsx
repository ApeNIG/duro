import { useState } from 'react'
import StatsGrid from '@/components/StatsGrid'
import ActivityFeed from '@/components/ActivityFeed'
import HealthPanel from '@/components/HealthPanel'
import AlertsPanel from '@/components/AlertsPanel'
import ArtifactModal from '@/components/ArtifactModal'
import { useHealth } from '@/hooks/useStats'

export default function Overview() {
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)
  const { data: health } = useHealth()

  return (
    <div className="h-full flex flex-col gap-6 min-h-0">
      {/* Terminal Header */}
      <div className="flex items-center justify-between">
        <div className="font-mono text-[13px] text-text-secondary">
          <span className="text-text-muted">$ </span>
          <span>duro status --overview</span>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px]">
          <span className={`w-1.5 h-1.5 rounded-full ${
            health?.database === 'connected' ? 'bg-accent' : 'bg-error'
          }`} />
          <span className={health?.database === 'connected' ? 'text-accent' : 'text-error'}>
            {health?.database === 'connected' ? 'connected' : 'disconnected'}
          </span>
        </div>
      </div>

      {/* Stats Row - Terminal Style */}
      <StatsGrid />

      {/* Divider */}
      <div className="h-px bg-border" />

      {/* Main Content */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-10 min-h-0">
        {/* Activity Feed - Left Column */}
        <div className="min-h-0 overflow-hidden">
          <ActivityFeed />
        </div>

        {/* Right Column - Alerts + Health */}
        <div className="flex flex-col gap-6 min-h-0 overflow-y-auto">
          <AlertsPanel />
          <HealthPanel />
        </div>
      </div>

      {/* Artifact Modal */}
      {selectedArtifactId && (
        <ArtifactModal
          artifactId={selectedArtifactId}
          onClose={() => setSelectedArtifactId(null)}
        />
      )}
    </div>
  )
}
