import { useState, useEffect } from 'react'
import { Database, ChevronDown, Loader2, Trash2, Square, CheckSquare } from 'lucide-react'
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

interface ArtifactCardProps {
  artifact: Artifact
  isSelected: boolean
  selectionMode: boolean
  onSelect: (id: string) => void
  onClick: () => void
}

function ArtifactCard({ artifact, isSelected, selectionMode, onSelect, onClick }: ArtifactCardProps) {
  const colorClasses = typeColors[artifact.type] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'

  const handleClick = (e: React.MouseEvent) => {
    if (selectionMode) {
      e.stopPropagation()
      onSelect(artifact.id)
    } else {
      onClick()
    }
  }

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onSelect(artifact.id)
  }

  return (
    <div
      className={`bg-card border rounded-lg p-3 transition-colors cursor-pointer group ${
        isSelected
          ? 'border-accent bg-accent/5'
          : 'border-border hover:border-accent/30'
      }`}
      onClick={handleClick}
    >
      <div className="flex items-start gap-2">
        {/* Checkbox */}
        <button
          onClick={handleCheckboxClick}
          className={`mt-0.5 flex-shrink-0 transition-opacity ${
            selectionMode || isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-50'
          }`}
        >
          {isSelected ? (
            <CheckSquare className="w-4 h-4 text-accent" />
          ) : (
            <Square className="w-4 h-4 text-text-secondary" />
          )}
        </button>

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

interface MemoryBrowserProps {
  fullPage?: boolean
}

export default function MemoryBrowser({ fullPage = false }: MemoryBrowserProps) {
  const [selectedType, setSelectedType] = useState<string>('all')
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [isDeleting, setIsDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const selectionMode = selectedIds.size > 0

  // Load initial data when type changes
  const loadArtifacts = () => {
    setIsLoading(true)
    setArtifacts([])
    setSelectedIds(new Set())

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
  }

  useEffect(() => {
    loadArtifacts()
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

  // Selection handlers
  const handleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleSelectAll = () => {
    if (selectedIds.size === artifacts.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(artifacts.map(a => a.id)))
    }
  }

  const handleClearSelection = () => {
    setSelectedIds(new Set())
  }

  // Delete handler
  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return

    setIsDeleting(true)
    try {
      const result = await api.bulkDelete(Array.from(selectedIds))
      if (result.success) {
        // Remove deleted artifacts from local state
        setArtifacts((prev) => prev.filter(a => !selectedIds.has(a.id)))
        setTotal((prev) => prev - result.deleted_count)
        setSelectedIds(new Set())
        setShowDeleteConfirm(false)
      }
    } catch (error) {
      console.error('Bulk delete failed:', error)
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div className={`bg-card border border-border rounded-lg flex flex-col min-h-0 overflow-hidden ${fullPage ? 'h-full' : 'h-full'}`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-accent" />
          <span className="text-sm font-medium">Memory Browser</span>
          <span className="text-xs text-text-secondary">
            ({artifacts.length}/{total} shown)
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Select All Toggle */}
          <button
            onClick={handleSelectAll}
            className="p-1.5 rounded hover:bg-white/10 text-text-secondary hover:text-text-primary transition-colors"
            title={selectedIds.size === artifacts.length ? 'Deselect all' : 'Select all'}
          >
            {selectedIds.size === artifacts.length && artifacts.length > 0 ? (
              <CheckSquare className="w-4 h-4 text-accent" />
            ) : (
              <Square className="w-4 h-4" />
            )}
          </button>

          {/* Type Filter */}
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
      </div>

      {/* Artifact List */}
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
              isSelected={selectedIds.has(artifact.id)}
              selectionMode={selectionMode}
              onSelect={handleSelect}
              onClick={() => setSelectedArtifactId(artifact.id)}
            />
          ))
        )}
      </div>

      {/* Load More / Bulk Actions */}
      {selectionMode ? (
        // Bulk Action Bar
        <div className="px-4 py-3 border-t border-border bg-page/50 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-primary">
              {selectedIds.size} selected
            </span>
            <button
              onClick={handleClearSelection}
              className="text-xs text-text-secondary hover:text-text-primary transition-colors"
            >
              Clear
            </button>
          </div>

          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-red-500/20 text-red-400 border border-red-500/30 rounded hover:bg-red-500/30 transition-colors text-sm"
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </button>
        </div>
      ) : hasMore ? (
        <div className="px-4 py-2 border-t border-border flex-shrink-0">
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
      ) : null}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-full bg-red-500/20">
                <Trash2 className="w-6 h-6 text-red-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-text-primary mb-2">
                  Delete {selectedIds.size} artifact{selectedIds.size > 1 ? 's' : ''}?
                </h3>
                <p className="text-sm text-text-secondary mb-4">
                  This action cannot be undone. The artifacts and their files will be permanently removed.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="flex-1 px-4 py-2 bg-page border border-border rounded text-sm text-text-primary hover:bg-white/5 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleBulkDelete}
                    disabled={isDeleting}
                    className="flex-1 px-4 py-2 bg-red-500/20 border border-red-500/30 rounded text-sm text-red-400 hover:bg-red-500/30 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {isDeleting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Deleting...
                      </>
                    ) : (
                      'Delete'
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Artifact Modal */}
      {selectedArtifactId && (
        <ArtifactModal
          artifactId={selectedArtifactId}
          onClose={() => setSelectedArtifactId(null)}
          onDelete={() => {
            // Refresh after delete
            loadArtifacts()
            setSelectedArtifactId(null)
          }}
        />
      )}
    </div>
  )
}
