import { useState, useEffect } from 'react'
import { CheckCircle, XCircle, AlertCircle, Clock, ChevronRight, Loader2, MessageSquare } from 'lucide-react'
import { api } from '@/lib/api'
import type { Artifact } from '@/lib/api'

interface Decision extends Artifact {
  decision?: string
  rationale?: string
  alternatives?: string[]
  context?: string
  outcome_status?: 'pending' | 'validated' | 'partial' | 'reversed' | 'superseded'
  confidence?: number
}

const statusColors = {
  pending: 'text-warning bg-warning/10 border-warning/30',
  validated: 'text-green-400 bg-green-500/10 border-green-500/30',
  partial: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  reversed: 'text-red-400 bg-red-500/10 border-red-500/30',
  superseded: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
}

function formatAge(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const days = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

  if (days === 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  if (days < 30) return `${Math.floor(days / 7)} weeks ago`
  return `${Math.floor(days / 30)} months ago`
}

function DecisionCard({
  decision,
  onReview,
}: {
  decision: Decision
  onReview: (id: string, status: 'validated' | 'partial' | 'reversed', notes: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [notes, setNotes] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const status = decision.outcome_status || 'pending'
  const statusClass = statusColors[status] || statusColors.pending

  const handleReview = async (newStatus: 'validated' | 'partial' | 'reversed') => {
    setIsSubmitting(true)
    await onReview(decision.id, newStatus, notes)
    setIsSubmitting(false)
    setExpanded(false)
    setNotes('')
  }

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className="p-4 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5">
            {status === 'pending' && <Clock className="w-5 h-5 text-warning" />}
            {status === 'validated' && <CheckCircle className="w-5 h-5 text-green-400" />}
            {status === 'reversed' && <XCircle className="w-5 h-5 text-red-400" />}
            {status === 'superseded' && <AlertCircle className="w-5 h-5 text-gray-400" />}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs px-2 py-0.5 rounded border ${statusClass}`}>
                {status}
              </span>
              <span className="text-xs text-text-secondary">
                {formatAge(decision.created_at)}
              </span>
              {decision.confidence && (
                <span className="text-xs text-text-secondary">
                  {(decision.confidence * 100).toFixed(0)}% confidence
                </span>
              )}
            </div>

            <h3 className="text-sm text-text-primary font-medium mb-1">
              {decision.title || decision.decision || decision.id}
            </h3>

            {decision.rationale && (
              <p className="text-xs text-text-secondary line-clamp-2">
                {decision.rationale}
              </p>
            )}

            {decision.tags && decision.tags.length > 0 && (
              <div className="flex gap-1 mt-2 flex-wrap">
                {decision.tags.slice(0, 4).map((tag) => (
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
            className={`w-5 h-5 text-text-secondary transition-transform ${
              expanded ? 'rotate-90' : ''
            }`}
          />
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="border-t border-border p-4 bg-page/50">
          {/* Decision Details */}
          {decision.context && (
            <div className="mb-4">
              <div className="text-xs text-text-secondary uppercase mb-1">Context</div>
              <p className="text-sm text-text-primary">{decision.context}</p>
            </div>
          )}

          {decision.alternatives && decision.alternatives.length > 0 && (
            <div className="mb-4">
              <div className="text-xs text-text-secondary uppercase mb-1">Alternatives Considered</div>
              <ul className="text-sm text-text-secondary list-disc list-inside">
                {decision.alternatives.map((alt, i) => (
                  <li key={i}>{alt}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Review Actions */}
          {status === 'pending' && (
            <div className="space-y-3">
              <div className="relative">
                <MessageSquare className="w-4 h-4 absolute left-3 top-3 text-text-secondary" />
                <textarea
                  placeholder="What was the outcome? (optional)"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  className="w-full bg-card border border-border rounded pl-10 pr-4 py-2 text-sm text-text-primary placeholder:text-text-secondary/50 focus:border-accent/50 focus:outline-none resize-none"
                />
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => handleReview('validated')}
                  disabled={isSubmitting}
                  className="flex-1 flex flex-col items-center justify-center gap-1 py-2 px-4 bg-green-500/20 text-green-400 border border-green-500/30 rounded hover:bg-green-500/30 transition-colors disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    {isSubmitting ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <CheckCircle className="w-4 h-4" />
                    )}
                    Worked
                  </span>
                  <span className="text-xs opacity-70">+10% confidence</span>
                </button>

                <button
                  onClick={() => handleReview('partial')}
                  disabled={isSubmitting}
                  className="flex-1 flex flex-col items-center justify-center gap-1 py-2 px-4 bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 rounded hover:bg-yellow-500/30 transition-colors disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    {isSubmitting ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <AlertCircle className="w-4 h-4" />
                    )}
                    Partial
                  </span>
                  <span className="text-xs opacity-70">no change</span>
                </button>

                <button
                  onClick={() => handleReview('reversed')}
                  disabled={isSubmitting}
                  className="flex-1 flex flex-col items-center justify-center gap-1 py-2 px-4 bg-red-500/20 text-red-400 border border-red-500/30 rounded hover:bg-red-500/30 transition-colors disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    {isSubmitting ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <XCircle className="w-4 h-4" />
                    )}
                    Didn't work
                  </span>
                  <span className="text-xs opacity-70">-10% confidence</span>
                </button>
              </div>
            </div>
          )}

          {/* Already Reviewed */}
          {status !== 'pending' && (
            <div className={`text-sm ${statusClass} p-3 rounded border`}>
              {status === 'validated' && 'This decision was marked as successful'}
              {status === 'partial' && 'This decision partially worked'}
              {status === 'reversed' && 'This decision was marked as unsuccessful'}
              {status === 'superseded' && 'This decision was superseded by another'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Reviews() {
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState<'pending' | 'all'>('pending')

  // Load decisions - use the /api/decisions endpoint which includes validation status
  const loadDecisions = async () => {
    setIsLoading(true)
    try {
      const data = await api.decisions({ limit: 100 })
      // Sort by created_at, oldest first for pending
      const sorted = data.decisions.sort((a, b) => {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      })
      setDecisions(sorted as Decision[])
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadDecisions()
  }, [])

  const handleReview = async (id: string, status: 'validated' | 'partial' | 'reversed', notes: string) => {
    // Call the backend to record the validation
    try {
      const response = await fetch('/api/reviews', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision_id: id, status, notes }),
      })

      if (!response.ok) {
        throw new Error('Failed to submit review')
      }

      // Reload decisions from server to get updated validation status
      await loadDecisions()
    } catch (error) {
      console.error('Failed to submit review:', error)
    }
  }

  const filteredDecisions = filter === 'pending'
    ? decisions.filter((d) => !d.outcome_status || d.outcome_status === 'pending')
    : decisions

  const pendingCount = decisions.filter(
    (d) => !d.outcome_status || d.outcome_status === 'pending'
  ).length

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-display font-semibold">Decision Review</h1>
          {pendingCount > 0 && (
            <span className="px-2 py-0.5 bg-warning/20 text-warning text-xs rounded-full">
              {pendingCount} pending
            </span>
          )}
        </div>

        {/* Filter */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFilter('pending')}
            className={`px-3 py-1.5 text-sm rounded transition-colors ${
              filter === 'pending'
                ? 'bg-accent text-page'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Pending
          </button>
          <button
            onClick={() => setFilter('all')}
            className={`px-3 py-1.5 text-sm rounded transition-colors ${
              filter === 'all'
                ? 'bg-accent text-page'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            All
          </button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-accent/10 border border-accent/30 rounded-lg p-4 mb-6">
        <p className="text-sm text-accent">
          <strong>Why review decisions?</strong> Your feedback closes the learning loop.
          Marking decisions as "worked" or "didn't work" helps me improve over time.
        </p>
      </div>

      {/* Decision List */}
      <div className="flex-1 overflow-auto min-h-0 space-y-3">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-text-secondary" />
          </div>
        ) : filteredDecisions.length === 0 ? (
          <div className="text-center py-12 text-text-secondary">
            {filter === 'pending'
              ? 'No decisions pending review'
              : 'No decisions found'}
          </div>
        ) : (
          filteredDecisions.map((decision) => (
            <DecisionCard
              key={decision.id}
              decision={decision}
              onReview={handleReview}
            />
          ))
        )}
      </div>
    </div>
  )
}
