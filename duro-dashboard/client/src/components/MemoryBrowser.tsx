import { useState, useEffect } from 'react'
import { Database, ChevronDown, Loader2 } from 'lucide-react'
import type { Artifact } from '@/lib/api'
import { api } from '@/lib/api'
import ArtifactModal from './ArtifactModal'

const typeColors: Record<string, string> = {
  fact: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  decision: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  episode: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  evaluation: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  skill: 'bg-green-500/20 text-green-400 border-green-500/30',
  rule: 'bg-red-500/20 text-red-400 border-red-500/30',
  log: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  skill_stats: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  incident: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
  recent_change: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
}

function formatDate(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function ArtifactCard({ artifact, onClick }: { artifact: Artifact; onClick: () => void }) {
  const colorClasses = typeColors[artifact.type] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'

  return (
    <div
      className="bg-card border border-border rounded-lg p-3 hover:border-accent/30 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className={`text-xs font-mono uppercase px-1.5 py-0.5 rounded border ${colorClasses}`}
            >
              {artifact.type}
            </span>
            <span className="text-xs text-text-secondary">{formatDate(artifact.created_at)}</span>
          </div>
          <div className="text-sm text-text-primary mt-1.5 truncate">
            {artifact.title || artifact.id}
          </div>
          {artifact.tags && artifact.tags.length > 0 && (
            <div className="flex gap-1 mt-2 flex-wrap">
              {artifact.tags.slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-1.5 py-0.5 bg-white/5 rounded text-text-secondary"
                >
                  {tag}
                </span>
              ))}
              {artifact.tags.length > 3 && (
                <span className="text-xs text-text-secondary/50">+{artifact.tags.length - 3}</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const ARTIFACT_TYPES = ['all', 'fact', 'decision', 'episode', 'evaluation', 'skill', 'rule', 'log', 'incident']

const PAGE_SIZE = 20

export default function MemoryBrowser() {
  const [selectedType, setSelectedType] = useState<string>('all')
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  // Load initial data when type changes
  useEffect(() => {
    setIsLoading(true)
    setArtifacts([])

    api.artifacts({
      type: selectedType === 'all' ? undefined : selectedType,
      limit: PAGE_SIZE,
      offset: 0,
    })
      .then((data) => {
        setArtifacts(data.artifacts)
        setTotal(data.total)
        setHasMore(data.has_more)
      })
      .finally(() => setIsLoading(false))
  }, [selectedType])

  // Load more handler
  const handleLoadMore = () => {
    if (isLoadingMore) return

    setIsLoadingMore(true)
    api.artifacts({
      type: selectedType === 'all' ? undefined : selectedType,
      limit: PAGE_SIZE,
      offset: artifacts.length,
    })
      .then((data) => {
        setArtifacts((prev) => [...prev, ...data.artifacts])
        setHasMore(data.has_more)
      })
      .finally(() => setIsLoadingMore(false))
  }

  return (
    <div className="bg-card border border-border rounded-lg h-full flex flex-col min-h-0 overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-accent" />
          <span className="text-sm font-medium">Memory Browser</span>
          <span className="text-xs text-text-secondary">
            ({artifacts.length}/{total} shown)
          </span>
        </div>

        <div className="relative">
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="appearance-none bg-page border border-border rounded px-3 py-1 pr-8 text-xs text-text-primary cursor-pointer hover:border-accent/50 transition-colors"
          >
            {ARTIFACT_TYPES.map((type) => (
              <option key={type} value={type}>
                {type === 'all' ? 'All Types' : type}
              </option>
            ))}
          </select>
          <ChevronDown className="w-3 h-3 absolute right-2 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {isLoading ? (
          <>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="bg-card border border-border rounded-lg p-3 animate-pulse">
                <div className="flex items-center gap-2">
                  <div className="w-12 h-5 bg-border rounded" />
                  <div className="w-24 h-3 bg-border rounded" />
                </div>
                <div className="w-3/4 h-4 bg-border rounded mt-2" />
              </div>
            ))}
          </>
        ) : artifacts.length === 0 ? (
          <div className="text-center text-text-secondary text-sm py-8">
            No artifacts found
          </div>
        ) : (
          artifacts.map((artifact) => (
            <ArtifactCard
              key={artifact.id}
              artifact={artifact}
              onClick={() => setSelectedArtifactId(artifact.id)}
            />
          ))
        )}
      </div>

      {hasMore && (
        <div className="px-4 py-2 border-t border-border">
          <button
            onClick={handleLoadMore}
            disabled={isLoadingMore}
            className="w-full text-xs text-accent hover:text-accent/80 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isLoadingMore ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                Loading...
              </>
            ) : (
              `Load more (${total - artifacts.length} remaining)`
            )}
          </button>
        </div>
      )}

      {selectedArtifactId && (
        <ArtifactModal
          artifactId={selectedArtifactId}
          onClose={() => setSelectedArtifactId(null)}
        />
      )}
    </div>
  )
}
