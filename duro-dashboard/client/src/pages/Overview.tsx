import { useState } from 'react'
import StatsGrid from '@/components/StatsGrid'
import ActivityFeed from '@/components/ActivityFeed'
import MemoryBrowser from '@/components/MemoryBrowser'
import InsightsPanel from '@/components/InsightsPanel'
import ArtifactModal from '@/components/ArtifactModal'

export default function Overview() {
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)

  return (
    <div className="h-full flex flex-col gap-4 lg:gap-6 min-h-0">
      {/* Stats Row */}
      <StatsGrid />

      {/* Insights Panel */}
      <InsightsPanel onSelectArtifact={setSelectedArtifactId} />

      {/* Main Content */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 min-h-0">
        <ActivityFeed />
        <MemoryBrowser />
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
