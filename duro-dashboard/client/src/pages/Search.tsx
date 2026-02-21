import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Search as SearchIcon,
  Loader2,
  Filter,
  ChevronDown,
  Sparkles,
  Clock,
  Tag,
  X,
  ArrowRight,
  Zap,
} from 'lucide-react'
import ArtifactModal from '@/components/ArtifactModal'

interface SearchHit {
  id: string
  type: string
  title: string | null
  tags: string[]
  created_at: string
  confidence?: number
  semantic_score?: number
  keyword_score?: number
  final_score?: number
  highlights?: string[]
  content?: Record<string, unknown>
}

interface SearchResponse {
  query: string
  hits: SearchHit[]
  total: number
  took_ms: number
  mode?: string
}

const typeColors: Record<string, string> = {
  fact: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  decision: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  episode: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  evaluation: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  skill: 'bg-green-500/20 text-green-400 border-green-500/30',
  log: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  skill_stats: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  incident_rca: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
  recent_change: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
}

const ARTIFACT_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'fact', label: 'Facts' },
  { value: 'decision', label: 'Decisions' },
  { value: 'episode', label: 'Episodes' },
  { value: 'evaluation', label: 'Evaluations' },
  { value: 'incident_rca', label: 'Incidents' },
  { value: 'recent_change', label: 'Changes' },
  { value: 'log', label: 'Logs' },
]

function formatDate(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'today'
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function ScoreBar({ score, label, color }: { score: number; label: string; color: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-text-secondary w-16">{label}</span>
      <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.min(score * 100, 100)}%` }}
        />
      </div>
      <span className="text-text-secondary w-8 text-right">{(score * 100).toFixed(0)}%</span>
    </div>
  )
}

function SearchHitCard({
  hit,
  onClick,
}: {
  hit: SearchHit
  onClick: () => void
}) {
  const colorClasses = typeColors[hit.type] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'

  return (
    <div
      className="bg-card border border-border rounded-lg p-4 hover:border-accent/30 transition-all cursor-pointer group"
      onClick={onClick}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          {/* Type and date */}
          <div className="flex items-center gap-2 mb-2">
            <span className={`text-xs font-mono uppercase px-1.5 py-0.5 rounded border ${colorClasses}`}>
              {hit.type.replace('_', ' ')}
            </span>
            <span className="text-xs text-text-secondary flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDate(hit.created_at)}
            </span>
            {hit.final_score !== undefined && (
              <span className="text-xs text-accent flex items-center gap-1 ml-auto">
                <Sparkles className="w-3 h-3" />
                {(hit.final_score * 100).toFixed(0)}% match
              </span>
            )}
          </div>

          {/* Title */}
          <h3 className="text-sm text-text-primary font-medium mb-2 line-clamp-2">
            {hit.title || hit.id}
          </h3>

          {/* Highlights */}
          {hit.highlights && hit.highlights.length > 0 && (
            <div className="text-xs text-text-secondary mb-2 space-y-1">
              {hit.highlights.slice(0, 2).map((h, i) => (
                <p key={i} className="line-clamp-1 bg-accent/5 px-2 py-1 rounded">
                  ...{h}...
                </p>
              ))}
            </div>
          )}

          {/* Tags */}
          {hit.tags && hit.tags.length > 0 && (
            <div className="flex items-center gap-1 flex-wrap">
              <Tag className="w-3 h-3 text-text-secondary/50" />
              {hit.tags.slice(0, 4).map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-1.5 py-0.5 bg-white/5 rounded text-text-secondary"
                >
                  {tag}
                </span>
              ))}
              {hit.tags.length > 4 && (
                <span className="text-xs text-text-secondary/50">+{hit.tags.length - 4}</span>
              )}
            </div>
          )}

          {/* Score breakdown (on hover) */}
          {(hit.semantic_score !== undefined || hit.keyword_score !== undefined) && (
            <div className="mt-3 pt-3 border-t border-border space-y-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {hit.semantic_score !== undefined && (
                <ScoreBar score={hit.semantic_score} label="Semantic" color="bg-purple-500" />
              )}
              {hit.keyword_score !== undefined && (
                <ScoreBar score={hit.keyword_score} label="Keyword" color="bg-blue-500" />
              )}
            </div>
          )}
        </div>

        <ArrowRight className="w-4 h-4 text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </div>
  )
}

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => clearTimeout(handler)
  }, [value, delay])

  return debouncedValue
}

export default function Search() {
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)
  const [recentSearches, setRecentSearches] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem('duro-recent-searches')
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  })

  const debouncedQuery = useDebounce(query, 300)

  const { data, isLoading, isFetching, error } = useQuery<SearchResponse>({
    queryKey: ['search', debouncedQuery, typeFilter],
    queryFn: async () => {
      if (!debouncedQuery.trim()) {
        return { query: '', hits: [], total: 0, took_ms: 0 }
      }

      const params = new URLSearchParams({ query: debouncedQuery.trim(), limit: '50' })
      if (typeFilter) params.set('type', typeFilter)

      const res = await fetch(`/api/search?${params}`)
      if (!res.ok) throw new Error('Search failed')
      return res.json()
    },
    enabled: true,
    staleTime: 30000,
  })

  const saveRecentSearch = useCallback((q: string) => {
    if (!q.trim()) return
    setRecentSearches((prev) => {
      const filtered = prev.filter((s) => s !== q)
      const updated = [q, ...filtered].slice(0, 5)
      localStorage.setItem('duro-recent-searches', JSON.stringify(updated))
      return updated
    })
  }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      saveRecentSearch(query.trim())
    }
  }

  const handleRecentClick = (q: string) => {
    setQuery(q)
    saveRecentSearch(q)
  }

  const clearRecentSearches = () => {
    setRecentSearches([])
    localStorage.removeItem('duro-recent-searches')
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Sparkles className="w-5 h-5 text-accent" />
        <h1 className="text-xl font-display font-semibold">Semantic Search</h1>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <SearchIcon className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary" />
            <input
              type="text"
              placeholder="Search your memory... (natural language supported)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-card border border-border rounded-lg pl-12 pr-12 py-3 text-text-primary placeholder:text-text-secondary/50 focus:border-accent/50 focus:outline-none text-sm"
              autoFocus
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Type Filter */}
          <div className="relative">
            <Filter className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="appearance-none bg-card border border-border rounded-lg pl-10 pr-10 py-3 text-sm text-text-primary cursor-pointer hover:border-accent/50 focus:outline-none"
            >
              {ARTIFACT_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" />
          </div>
        </div>
      </form>

      {/* Recent Searches */}
      {!query && recentSearches.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-text-secondary uppercase">Recent searches</span>
            <button
              onClick={clearRecentSearches}
              className="text-xs text-text-secondary hover:text-text-primary transition-colors"
            >
              Clear
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {recentSearches.map((q) => (
              <button
                key={q}
                onClick={() => handleRecentClick(q)}
                className="px-3 py-1.5 bg-card border border-border rounded-full text-sm text-text-secondary hover:text-text-primary hover:border-accent/30 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Search Tips */}
      {!query && (
        <div className="mb-6 bg-accent/5 border border-accent/20 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Zap className="w-5 h-5 text-accent flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-medium text-text-primary mb-2">Search Tips</h3>
              <ul className="text-xs text-text-secondary space-y-1">
                <li>Use natural language: "decisions about authentication"</li>
                <li>Search by concept: "rate limiting strategies"</li>
                <li>Find related content: "errors in the deploy process"</li>
                <li>Semantic search finds meaning, not just keywords</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {isLoading && query && (
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-3 text-text-secondary">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Searching...</span>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-4">
          <p className="text-sm text-red-400">Search failed. Please try again.</p>
        </div>
      )}

      {/* Results */}
      {data && query && !isLoading && (
        <div className="flex-1 overflow-auto min-h-0">
          {/* Results Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm text-text-secondary">
              {data.total} result{data.total !== 1 ? 's' : ''} for "{data.query}"
              {isFetching && <Loader2 className="w-3 h-3 animate-spin inline ml-2" />}
            </div>
            <div className="text-xs text-text-secondary/50">
              {data.took_ms?.toFixed(0)}ms {data.mode && `• ${data.mode}`}
            </div>
          </div>

          {/* Results List */}
          {data.hits.length === 0 ? (
            <div className="text-center py-12">
              <SearchIcon className="w-12 h-12 text-text-secondary/30 mx-auto mb-4" />
              <p className="text-text-secondary">No results found</p>
              <p className="text-xs text-text-secondary/50 mt-1">Try different keywords or broaden your search</p>
            </div>
          ) : (
            <div className="grid gap-3">
              {data.hits.map((hit) => (
                <SearchHitCard
                  key={hit.id}
                  hit={hit}
                  onClick={() => setSelectedArtifactId(hit.id)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!query && !isLoading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Sparkles className="w-16 h-16 text-accent/20 mx-auto mb-4" />
            <p className="text-text-secondary">Start typing to search your memory</p>
          </div>
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
