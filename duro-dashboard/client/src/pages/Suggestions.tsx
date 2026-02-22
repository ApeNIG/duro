import { useState, useEffect } from 'react'
import { Link2, Check, X, Loader2, GitBranch, Target, Database, Lightbulb } from 'lucide-react'

interface Artifact {
  id: string
  type: string
  title: string
}

interface Suggestion {
  type: string
  source: Artifact
  target: Artifact
  score: number
  reason: string
  suggested_link: string
}

interface SuggestionsResponse {
  suggestions: Suggestion[]
  total: number
  by_type: Record<string, number>
  stats: {
    decisions_analyzed: number
    episodes_analyzed: number
    facts_analyzed: number
  }
}

const typeIcons: Record<string, React.ReactNode> = {
  decision: <GitBranch className="w-4 h-4" />,
  episode: <Target className="w-4 h-4" />,
  fact: <Database className="w-4 h-4" />,
}

const typeColors: Record<string, string> = {
  decision: 'text-violet-400 bg-violet-500/10 border-violet-500/30',
  episode: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
  fact: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
}

function SuggestionCard({
  suggestion,
  onApply,
  onDismiss,
}: {
  suggestion: Suggestion
  onApply: (s: Suggestion) => Promise<void>
  onDismiss: (s: Suggestion) => Promise<void>
}) {
  const [isApplying, setIsApplying] = useState(false)
  const [isDismissing, setIsDismissing] = useState(false)
  const [status, setStatus] = useState<'pending' | 'applied' | 'dismissed'>('pending')

  const handleApply = async () => {
    setIsApplying(true)
    try {
      await onApply(suggestion)
      setStatus('applied')
    } finally {
      setIsApplying(false)
    }
  }

  const handleDismiss = async () => {
    setIsDismissing(true)
    try {
      await onDismiss(suggestion)
      setStatus('dismissed')
    } finally {
      setIsDismissing(false)
    }
  }

  if (status === 'applied') {
    return (
      <div className="bg-accent/10 border border-accent/30 rounded-lg p-4">
        <div className="flex items-center gap-2 text-accent">
          <Check className="w-5 h-5" />
          <span>Link created between {suggestion.source.type} and {suggestion.target.type}</span>
        </div>
      </div>
    )
  }

  if (status === 'dismissed') {
    return (
      <div className="bg-white/5 border border-border rounded-lg p-4 opacity-50">
        <div className="flex items-center gap-2 text-text-secondary">
          <X className="w-5 h-5" />
          <span>Dismissed</span>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      <div className="p-4">
        {/* Score and Reason */}
        <div className="flex items-center gap-3 mb-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-accent/20 text-accent font-bold">
            {Math.round(suggestion.score * 100)}%
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs text-text-secondary mb-1">
              {suggestion.suggested_link.replace(/_/g, ' ')}
            </div>
            <div className="text-sm text-text-primary">{suggestion.reason}</div>
          </div>
        </div>

        {/* Source and Target */}
        <div className="flex items-center gap-2 mb-4">
          {/* Source */}
          <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded border ${typeColors[suggestion.source.type]}`}>
            {typeIcons[suggestion.source.type]}
            <span className="text-xs font-medium truncate max-w-[140px]">
              {suggestion.source.title}
            </span>
          </div>

          <span className="text-text-secondary">→</span>

          {/* Target */}
          <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded border ${typeColors[suggestion.target.type]}`}>
            {typeIcons[suggestion.target.type]}
            <span className="text-xs font-medium truncate max-w-[140px]">
              {suggestion.target.title}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={handleApply}
            disabled={isApplying || isDismissing}
            className="flex-1 flex items-center justify-center gap-2 py-2 px-4 bg-accent/20 text-accent border border-accent/30 rounded hover:bg-accent/30 transition-colors disabled:opacity-50"
          >
            {isApplying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Link2 className="w-4 h-4" />
            )}
            Apply Link
          </button>

          <button
            onClick={handleDismiss}
            disabled={isApplying || isDismissing}
            className="flex items-center justify-center gap-2 py-2 px-4 bg-white/5 text-text-secondary border border-border rounded hover:bg-white/10 transition-colors disabled:opacity-50"
          >
            {isDismissing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <X className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Suggestions() {
  const [data, setData] = useState<SuggestionsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [minScore, setMinScore] = useState(0.2)

  const loadSuggestions = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/suggestions/links?min_score=${minScore}&limit=30`)
      if (!response.ok) throw new Error('Failed to load suggestions')
      const result = await response.json()
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadSuggestions()
  }, [minScore])

  const handleApply = async (suggestion: Suggestion) => {
    const response = await fetch('/api/suggestions/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_id: suggestion.source.id,
        target_id: suggestion.target.id,
        link_type: suggestion.suggested_link,
      }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to apply link')
    }
  }

  const handleDismiss = async (suggestion: Suggestion) => {
    const response = await fetch('/api/suggestions/dismiss', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_id: suggestion.source.id,
        target_id: suggestion.target.id,
      }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to dismiss suggestion')
    }
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Lightbulb className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-display font-semibold">Link Suggestions</h1>
          {data && (
            <span className="px-2 py-0.5 bg-accent/20 text-accent text-xs rounded-full">
              {data.total} found
            </span>
          )}
        </div>

        {/* Score Filter */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-secondary">Min score:</span>
          <select
            value={minScore}
            onChange={(e) => setMinScore(parseFloat(e.target.value))}
            className="bg-card border border-border rounded px-2 py-1 text-sm"
          >
            <option value={0.1}>10%</option>
            <option value={0.2}>20%</option>
            <option value={0.3}>30%</option>
            <option value={0.4}>40%</option>
            <option value={0.5}>50%</option>
          </select>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-accent/10 border border-accent/30 rounded-lg p-4 mb-6">
        <p className="text-sm text-accent">
          <strong>Auto-link Suggestions</strong> finds potential connections between artifacts
          using tag overlap, keyword matching, and temporal proximity. Apply links to strengthen
          the knowledge graph or dismiss to hide suggestions.
        </p>
      </div>

      {/* Stats */}
      {data && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-2xl font-bold text-text-primary">{data.total}</div>
            <div className="text-xs text-text-secondary">Suggestions</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-2xl font-bold text-text-primary">{data.stats.decisions_analyzed}</div>
            <div className="text-xs text-text-secondary">Decisions</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-2xl font-bold text-text-primary">{data.stats.episodes_analyzed}</div>
            <div className="text-xs text-text-secondary">Episodes</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-2xl font-bold text-text-primary">{data.stats.facts_analyzed}</div>
            <div className="text-xs text-text-secondary">Facts</div>
          </div>
        </div>
      )}

      {/* Type Breakdown */}
      {data && Object.keys(data.by_type).length > 0 && (
        <div className="flex gap-2 mb-4">
          {Object.entries(data.by_type).map(([type, count]) => (
            <span
              key={type}
              className="text-xs px-2 py-1 bg-white/5 text-text-secondary rounded border border-border"
            >
              {type.replace(/_/g, ' ')}: {count}
            </span>
          ))}
        </div>
      )}

      {/* Suggestions List */}
      <div className="flex-1 overflow-auto min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-text-secondary" />
          </div>
        ) : error ? (
          <div className="text-center py-12 text-error">{error}</div>
        ) : !data || data.suggestions.length === 0 ? (
          <div className="text-center py-12 text-text-secondary">
            No link suggestions found. Try lowering the minimum score threshold.
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {data.suggestions.map((suggestion, i) => (
              <SuggestionCard
                key={`${suggestion.source.id}-${suggestion.target.id}-${i}`}
                suggestion={suggestion}
                onApply={handleApply}
                onDismiss={handleDismiss}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
