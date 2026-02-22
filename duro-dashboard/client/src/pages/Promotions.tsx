import { useState, useEffect } from 'react'
import { ArrowUpCircle, CheckCircle, Loader2, TrendingUp, Scale, Wrench, ChevronRight } from 'lucide-react'

interface PromotionCandidate {
  decision_id: string
  decision_text: string
  confidence: number
  validation_count: number
  status: string
  tags: string[]
  created_at: string
  last_validated: string | null
  promotion_score: number
  promotion_ready: boolean
  suggested_type: 'law' | 'pattern' | 'skill'
}

interface PromotionsResponse {
  candidates: PromotionCandidate[]
  total: number
  ready_count: number
  stats: {
    avg_confidence: number
    avg_validations: number
    by_type: {
      law: number
      pattern: number
      skill: number
    }
  }
}

const typeIcons = {
  law: <Scale className="w-4 h-4" />,
  pattern: <TrendingUp className="w-4 h-4" />,
  skill: <Wrench className="w-4 h-4" />,
}

const typeColors = {
  law: 'text-red-400 bg-red-500/10 border-red-500/30',
  pattern: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  skill: 'text-green-400 bg-green-500/10 border-green-500/30',
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

function CandidateCard({
  candidate,
  onPromote,
}: {
  candidate: PromotionCandidate
  onPromote: (id: string, type: string) => Promise<void>
}) {
  const [expanded, setExpanded] = useState(false)
  const [isPromoting, setIsPromoting] = useState(false)
  const [promoted, setPromoted] = useState(false)

  const typeClass = typeColors[candidate.suggested_type]

  const handlePromote = async (type: string) => {
    setIsPromoting(true)
    try {
      await onPromote(candidate.decision_id, type)
      setPromoted(true)
    } finally {
      setIsPromoting(false)
    }
  }

  if (promoted) {
    return (
      <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
        <div className="flex items-center gap-2 text-green-400">
          <CheckCircle className="w-5 h-5" />
          <span>Promoted to {candidate.suggested_type}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className="p-4 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-3">
          {/* Score Badge */}
          <div className={`flex flex-col items-center justify-center w-12 h-12 rounded-lg ${
            candidate.promotion_ready ? 'bg-accent/20 text-accent' : 'bg-white/5 text-text-secondary'
          }`}>
            <span className="text-lg font-bold">{candidate.promotion_score}</span>
            <span className="text-[10px] uppercase">score</span>
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className={`text-xs px-2 py-0.5 rounded border flex items-center gap-1 ${typeClass}`}>
                {typeIcons[candidate.suggested_type]}
                {candidate.suggested_type}
              </span>
              <span className="text-xs text-text-secondary">
                {(candidate.confidence * 100).toFixed(0)}% conf
              </span>
              <span className="text-xs text-text-secondary">
                {candidate.validation_count} validations
              </span>
            </div>

            <h3 className="text-sm text-text-primary font-medium line-clamp-2">
              {candidate.decision_text}
            </h3>

            {candidate.tags.length > 0 && (
              <div className="flex gap-1 mt-2 flex-wrap">
                {candidate.tags.slice(0, 3).map((tag) => (
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

          <ChevronRight
            className={`w-5 h-5 text-text-secondary transition-transform flex-shrink-0 ${
              expanded ? 'rotate-90' : ''
            }`}
          />
        </div>
      </div>

      {/* Expanded Actions */}
      {expanded && (
        <div className="border-t border-border p-4 bg-page/50">
          <div className="text-xs text-text-secondary mb-3">
            Last validated: {candidate.last_validated ? formatDate(candidate.last_validated) : 'Never'}
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => handlePromote('law')}
              disabled={isPromoting}
              className="flex-1 flex items-center justify-center gap-2 py-2 px-4 bg-red-500/20 text-red-400 border border-red-500/30 rounded hover:bg-red-500/30 transition-colors disabled:opacity-50"
            >
              {isPromoting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Scale className="w-4 h-4" />}
              Promote to Law
            </button>

            <button
              onClick={() => handlePromote('pattern')}
              disabled={isPromoting}
              className="flex-1 flex items-center justify-center gap-2 py-2 px-4 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded hover:bg-blue-500/30 transition-colors disabled:opacity-50"
            >
              {isPromoting ? <Loader2 className="w-4 h-4 animate-spin" /> : <TrendingUp className="w-4 h-4" />}
              Promote to Pattern
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Promotions() {
  const [data, setData] = useState<PromotionsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadPromotions = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/promotions?min_confidence=0.7&min_validations=1&limit=20')
      if (!response.ok) throw new Error('Failed to load promotions')
      const result = await response.json()
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadPromotions()
  }, [])

  const handlePromote = async (decisionId: string, targetType: string) => {
    const response = await fetch('/api/promotions/promote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        decision_id: decisionId,
        target_type: targetType,
        project_id: 'duro',
      }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to promote')
    }
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <ArrowUpCircle className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-display font-semibold">Promotion Pipeline</h1>
          {data && data.ready_count > 0 && (
            <span className="px-2 py-0.5 bg-accent/20 text-accent text-xs rounded-full">
              {data.ready_count} ready
            </span>
          )}
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-accent/10 border border-accent/30 rounded-lg p-4 mb-6">
        <p className="text-sm text-accent">
          <strong>Promotion Pipeline</strong> surfaces validated decisions ready to become
          permanent laws or patterns. Score = confidence × 10 + validations × 2. Ready at 10+.
        </p>
      </div>

      {/* Stats */}
      {data && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-2xl font-bold text-text-primary">{data.total}</div>
            <div className="text-xs text-text-secondary">Candidates</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-2xl font-bold text-accent">{data.ready_count}</div>
            <div className="text-xs text-text-secondary">Ready</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-2xl font-bold text-text-primary">{(data.stats.avg_confidence * 100).toFixed(0)}%</div>
            <div className="text-xs text-text-secondary">Avg Confidence</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-2xl font-bold text-text-primary">{data.stats.avg_validations}</div>
            <div className="text-xs text-text-secondary">Avg Validations</div>
          </div>
        </div>
      )}

      {/* Type Breakdown */}
      {data && (
        <div className="flex gap-2 mb-4">
          <span className="text-xs px-2 py-1 bg-red-500/10 text-red-400 rounded border border-red-500/30">
            {data.stats.by_type.law} laws
          </span>
          <span className="text-xs px-2 py-1 bg-blue-500/10 text-blue-400 rounded border border-blue-500/30">
            {data.stats.by_type.pattern} patterns
          </span>
          <span className="text-xs px-2 py-1 bg-green-500/10 text-green-400 rounded border border-green-500/30">
            {data.stats.by_type.skill} skills
          </span>
        </div>
      )}

      {/* Candidates List */}
      <div className="flex-1 overflow-auto min-h-0 space-y-3">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-text-secondary" />
          </div>
        ) : error ? (
          <div className="text-center py-12 text-error">{error}</div>
        ) : !data || data.candidates.length === 0 ? (
          <div className="text-center py-12 text-text-secondary">
            No promotion candidates found. Validate more decisions to build the pipeline.
          </div>
        ) : (
          data.candidates.map((candidate) => (
            <CandidateCard
              key={candidate.decision_id}
              candidate={candidate}
              onPromote={handlePromote}
            />
          ))
        )}
      </div>
    </div>
  )
}
