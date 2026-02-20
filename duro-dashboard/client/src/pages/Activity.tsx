import { useState, useEffect } from 'react'
import { Zap, Circle, Calendar, ChevronDown, Loader2, RefreshCw } from 'lucide-react'
import { useActivity } from '@/hooks/useActivity'
import type { Artifact } from '@/lib/api'
import { api } from '@/lib/api'
import ArtifactModal from '@/components/ArtifactModal'

const typeColors: Record<string, string> = {
  fact: 'text-blue-400',
  decision: 'text-purple-400',
  episode: 'text-orange-400',
  evaluation: 'text-yellow-400',
  skill: 'text-green-400',
  rule: 'text-red-400',
  log: 'text-gray-400',
  skill_stats: 'text-cyan-400',
  incident_rca: 'text-rose-400',
  recent_change: 'text-amber-400',
  decision_validation: 'text-indigo-400',
}

const TIME_RANGES = [
  { label: 'Last hour', value: 1 },
  { label: 'Last 24 hours', value: 24 },
  { label: 'Last 7 days', value: 168 },
  { label: 'Last 30 days', value: 720 },
]

function formatTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return 'just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function ActivityItem({ artifact, onClick }: { artifact: Artifact; onClick: () => void }) {
  const colorClass = typeColors[artifact.type] || 'text-text-secondary'

  return (
    <div
      className="flex items-start gap-3 py-3 px-4 hover:bg-white/5 rounded transition-colors cursor-pointer border-b border-border last:border-0"
      onClick={onClick}
    >
      <Circle className={`w-2 h-2 mt-2 fill-current ${colorClass}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-xs font-mono uppercase ${colorClass}`}>{artifact.type}</span>
          <span className="text-xs text-text-secondary/50">{formatTime(artifact.created_at)}</span>
        </div>
        <div className="text-sm text-text-primary truncate">
          {artifact.title || artifact.id}
        </div>
        {artifact.tags && artifact.tags.length > 0 && (
          <div className="flex gap-1 mt-1.5 flex-wrap">
            {artifact.tags.slice(0, 4).map((tag) => (
              <span
                key={tag}
                className="text-xs px-1.5 py-0.5 bg-white/5 rounded text-text-secondary"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function Activity() {
  const [timeRange, setTimeRange] = useState(24)
  const [hideLogs, setHideLogs] = useState(true)
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)
  const [historicalData, setHistoricalData] = useState<Artifact[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Live activity from SSE
  const { events: liveEvents, connected } = useActivity()

  // Load historical data
  useEffect(() => {
    setIsLoading(true)
    const since = new Date(Date.now() - timeRange * 60 * 60 * 1000).toISOString()

    api.artifacts({ limit: 100, offset: 0 })
      .then((data) => {
        // Filter by time range client-side
        const filtered = data.artifacts.filter(a => {
          const created = new Date(a.created_at)
          const cutoff = new Date(since)
          const inRange = created >= cutoff
          const passesLogFilter = !hideLogs || a.type !== 'log'
          return inRange && passesLogFilter
        })
        setHistoricalData(filtered)
      })
      .finally(() => setIsLoading(false))
  }, [timeRange, hideLogs])

  // Combine live + historical, dedupe by id
  const allActivity = [...liveEvents, ...historicalData]
    .filter((item, index, self) => self.findIndex(t => t.id === item.id) === index)
    .filter(item => !hideLogs || item.type !== 'log')
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 100)

  const refresh = () => {
    setIsLoading(true)
    api.artifacts({ limit: 100, offset: 0 })
      .then((data) => {
        const since = new Date(Date.now() - timeRange * 60 * 60 * 1000)
        const filtered = data.artifacts.filter(a => {
          const created = new Date(a.created_at)
          const inRange = created >= since
          const passesLogFilter = !hideLogs || a.type !== 'log'
          return inRange && passesLogFilter
        })
        setHistoricalData(filtered)
      })
      .finally(() => setIsLoading(false))
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Zap className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-display font-semibold">Activity</h1>
          <div className="flex items-center gap-1.5 ml-2">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-accent' : 'bg-error'}`} />
            <span className="text-xs text-text-secondary">
              {connected ? 'live' : 'disconnected'}
            </span>
          </div>
        </div>

        <button
          onClick={refresh}
          disabled={isLoading}
          className="p-2 text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4">
        {/* Time Range */}
        <div className="relative">
          <Calendar className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" />
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(Number(e.target.value))}
            className="appearance-none bg-card border border-border rounded pl-10 pr-8 py-2 text-sm text-text-primary cursor-pointer hover:border-accent/50 focus:outline-none"
          >
            {TIME_RANGES.map((range) => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>
          <ChevronDown className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" />
        </div>

        {/* Hide Logs */}
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={hideLogs}
            onChange={(e) => setHideLogs(e.target.checked)}
            className="w-4 h-4 rounded border-border bg-card accent-accent"
          />
          Hide logs
        </label>

        <span className="text-sm text-text-secondary ml-auto">
          {allActivity.length} events
        </span>
      </div>

      {/* Activity List */}
      <div className="flex-1 overflow-auto min-h-0 bg-card border border-border rounded-lg">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-text-secondary" />
          </div>
        ) : allActivity.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-text-secondary">
            No activity in this time range
          </div>
        ) : (
          <div className="divide-y divide-border">
            {allActivity.map((item) => (
              <ActivityItem
                key={item.id}
                artifact={item}
                onClick={() => setSelectedArtifactId(item.id)}
              />
            ))}
          </div>
        )}
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
