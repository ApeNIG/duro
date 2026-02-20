import { useState, useEffect } from 'react'
import { Database, Search, Filter, ChevronDown, Loader2, X } from 'lucide-react'
import type { Artifact } from '@/lib/api'
import { api } from '@/lib/api'
import ArtifactModal from '@/components/ArtifactModal'

const typeColors: Record<string, string> = {
  fact: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  decision: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  episode: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  evaluation: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  skill: 'bg-green-500/20 text-green-400 border-green-500/30',
  rule: 'bg-red-500/20 text-red-400 border-red-500/30',
  log: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  skill_stats: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  incident_rca: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
  recent_change: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  decision_validation: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
}

const ARTIFACT_TYPES = [
  'all', 'fact', 'decision', 'episode', 'evaluation',
  'log', 'skill', 'rule', 'incident_rca', 'recent_change'
]

function formatDate(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function ArtifactRow({ artifact, onClick }: { artifact: Artifact; onClick: () => void }) {
  const colorClasses = typeColors[artifact.type] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'

  return (
    <tr
      className="border-b border-border hover:bg-white/5 cursor-pointer transition-colors"
      onClick={onClick}
    >
      <td className="py-3 px-4">
        <span className={`text-xs font-mono uppercase px-2 py-1 rounded border ${colorClasses}`}>
          {artifact.type}
        </span>
      </td>
      <td className="py-3 px-4 text-sm text-text-primary max-w-md truncate">
        {artifact.title || artifact.id}
      </td>
      <td className="py-3 px-4">
        {artifact.tags && artifact.tags.length > 0 && (
          <div className="flex gap-1 flex-wrap">
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
      </td>
      <td className="py-3 px-4 text-xs text-text-secondary whitespace-nowrap">
        {formatDate(artifact.created_at)}
      </td>
    </tr>
  )
}

const PAGE_SIZE = 50

export default function Memory() {
  const [selectedType, setSelectedType] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [hideLogs, setHideLogs] = useState(true)
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  // Computed type filter
  const effectiveType = selectedType === 'all'
    ? (hideLogs ? 'no_logs' : undefined)
    : selectedType

  // Load data when filters change
  useEffect(() => {
    setIsLoading(true)
    setArtifacts([])

    api.artifacts({
      type: effectiveType === 'no_logs' ? undefined : effectiveType,
      search: searchQuery || undefined,
      limit: PAGE_SIZE,
      offset: 0,
    })
      .then((data) => {
        // Client-side filter for no_logs (until backend supports it)
        const filtered = effectiveType === 'no_logs'
          ? data.artifacts.filter(a => a.type !== 'log')
          : data.artifacts
        setArtifacts(filtered)
        setTotal(data.total)
        setHasMore(data.has_more)
      })
      .finally(() => setIsLoading(false))
  }, [effectiveType, searchQuery])

  const handleLoadMore = () => {
    if (isLoadingMore) return

    setIsLoadingMore(true)
    api.artifacts({
      type: effectiveType === 'no_logs' ? undefined : effectiveType,
      search: searchQuery || undefined,
      limit: PAGE_SIZE,
      offset: artifacts.length,
    })
      .then((data) => {
        const filtered = effectiveType === 'no_logs'
          ? data.artifacts.filter(a => a.type !== 'log')
          : data.artifacts
        setArtifacts((prev) => [...prev, ...filtered])
        setHasMore(data.has_more)
      })
      .finally(() => setIsLoadingMore(false))
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Database className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-display font-semibold">Memory</h1>
          <span className="text-sm text-text-secondary">
            {artifacts.length} of {total} artifacts
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
          <input
            type="text"
            placeholder="Search artifacts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-card border border-border rounded pl-10 pr-4 py-2 text-sm text-text-primary placeholder:text-text-secondary/50 focus:border-accent/50 focus:outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Type Filter */}
        <div className="relative">
          <Filter className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" />
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="appearance-none bg-card border border-border rounded pl-10 pr-8 py-2 text-sm text-text-primary cursor-pointer hover:border-accent/50 focus:outline-none"
          >
            {ARTIFACT_TYPES.map((type) => (
              <option key={type} value={type}>
                {type === 'all' ? 'All Types' : type}
              </option>
            ))}
          </select>
          <ChevronDown className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" />
        </div>

        {/* Hide Logs Toggle */}
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={hideLogs}
            onChange={(e) => setHideLogs(e.target.checked)}
            className="w-4 h-4 rounded border-border bg-card accent-accent"
          />
          Hide logs
        </label>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto min-h-0 bg-card border border-border rounded-lg">
        <table className="w-full">
          <thead className="sticky top-0 bg-card border-b border-border">
            <tr className="text-xs text-text-secondary uppercase">
              <th className="py-3 px-4 text-left font-medium">Type</th>
              <th className="py-3 px-4 text-left font-medium">Title</th>
              <th className="py-3 px-4 text-left font-medium">Tags</th>
              <th className="py-3 px-4 text-left font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={4} className="py-12 text-center">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto text-text-secondary" />
                </td>
              </tr>
            ) : artifacts.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-12 text-center text-text-secondary">
                  No artifacts found
                </td>
              </tr>
            ) : (
              artifacts.map((artifact) => (
                <ArtifactRow
                  key={artifact.id}
                  artifact={artifact}
                  onClick={() => setSelectedArtifactId(artifact.id)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Load More */}
      {hasMore && !isLoading && (
        <div className="mt-4 text-center">
          <button
            onClick={handleLoadMore}
            disabled={isLoadingMore}
            className="px-4 py-2 text-sm text-accent hover:text-accent/80 transition-colors disabled:opacity-50 flex items-center gap-2 mx-auto"
          >
            {isLoadingMore ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading...
              </>
            ) : (
              `Load more (${total - artifacts.length} remaining)`
            )}
          </button>
        </div>
      )}

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
