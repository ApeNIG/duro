import { useState, useEffect } from 'react'
import { Lightbulb, RefreshCw, AlertTriangle, CheckCircle, X, Clock, FileText, Brain, Zap } from 'lucide-react'
import { useInsights } from '@/hooks/useInsights'
import { ActionItem } from '@/lib/api'

const DISMISSED_KEY = 'duro-dismissed-insights'

function getDismissedItems(): Set<string> {
  try {
    const stored = localStorage.getItem(DISMISSED_KEY)
    if (stored) {
      return new Set(JSON.parse(stored))
    }
  } catch {
    // Ignore parse errors
  }
  return new Set()
}

function setDismissedItems(items: Set<string>) {
  localStorage.setItem(DISMISSED_KEY, JSON.stringify([...items]))
}

function ActionItemRow({
  item,
  onDismiss,
  onClick,
}: {
  item: ActionItem
  onDismiss: () => void
  onClick: () => void
}) {
  const priorityColors = {
    high: 'text-red-400 bg-red-400/10 border-red-400/20',
    medium: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
    low: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
  }

  return (
    <div
      className="flex items-center gap-3 py-2 px-3 hover:bg-white/5 rounded transition-colors cursor-pointer group"
      onClick={onClick}
    >
      <AlertTriangle className={`w-4 h-4 flex-shrink-0 ${priorityColors[item.priority].split(' ')[0]}`} />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-text-primary truncate">{item.title}</div>
        <div className="text-xs text-text-secondary/60">{item.age_days} days old</div>
      </div>
      <span className={`px-2 py-0.5 text-xs rounded border ${priorityColors[item.priority]}`}>
        {item.priority}
      </span>
      <button
        onClick={(e) => {
          e.stopPropagation()
          onDismiss()
        }}
        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-white/10 rounded transition-all"
        title="Dismiss"
      >
        <X className="w-3 h-3 text-text-secondary" />
      </button>
    </div>
  )
}

interface InsightsPanelProps {
  onSelectArtifact?: (id: string) => void
}

export default function InsightsPanel({ onSelectArtifact }: InsightsPanelProps) {
  const { data, isLoading, refetch, isFetching } = useInsights()
  const [dismissed, setDismissed] = useState<Set<string>>(() => getDismissedItems())

  // Persist dismissed items
  useEffect(() => {
    setDismissedItems(dismissed)
  }, [dismissed])

  const handleDismiss = (id: string) => {
    setDismissed((prev) => new Set([...prev, id]))
  }

  const handleClick = (id: string) => {
    if (onSelectArtifact) {
      onSelectArtifact(id)
    }
  }

  const visibleItems = data?.action_items.filter((item) => !dismissed.has(item.id)) || []

  if (isLoading) {
    return (
      <div className="bg-card border border-border rounded-lg p-4">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-4 h-4 bg-border rounded animate-pulse" />
          <div className="w-32 h-4 bg-border rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-4 gap-3 mb-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-12 bg-border rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  const summary = data?.summary

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Lightbulb className="w-4 h-4 text-accent" />
          <span className="text-sm font-medium">Proactive Insights</span>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="p-1.5 hover:bg-white/10 rounded transition-colors disabled:opacity-50"
          title="Refresh"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-text-secondary ${isFetching ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Summary Stats */}
      <div className="px-4 py-3 border-b border-border">
        <div className="grid grid-cols-4 gap-4 text-center">
          <div>
            <div className="flex items-center justify-center gap-1.5 text-lg font-semibold">
              <FileText className="w-4 h-4 text-green-400" />
              {summary?.total_facts.toLocaleString() || 0}
            </div>
            <div className="text-xs text-text-secondary">facts</div>
          </div>
          <div>
            <div className="flex items-center justify-center gap-1.5 text-lg font-semibold">
              <Brain className="w-4 h-4 text-purple-400" />
              {summary?.total_decisions.toLocaleString() || 0}
            </div>
            <div className="text-xs text-text-secondary">decisions</div>
          </div>
          <div>
            <div className="flex items-center justify-center gap-1.5 text-lg font-semibold">
              <Clock className="w-4 h-4 text-orange-400" />
              {summary?.pending_review || 0}
            </div>
            <div className="text-xs text-text-secondary">pending</div>
          </div>
          <div>
            <div className="flex items-center justify-center gap-1.5 text-lg font-semibold">
              <Zap className="w-4 h-4 text-cyan-400" />
              {summary?.recent_24h || 0}
            </div>
            <div className="text-xs text-text-secondary">24h</div>
          </div>
        </div>
      </div>

      {/* Action Items */}
      <div className="px-4 py-3">
        <div className="text-xs font-medium text-text-secondary uppercase tracking-wide mb-2">
          Needs Attention ({visibleItems.length})
        </div>

        {visibleItems.length === 0 ? (
          <div className="py-4 text-center">
            <CheckCircle className="w-8 h-8 text-accent mx-auto mb-2" />
            <div className="text-sm text-text-primary">All clear</div>
            <div className="text-xs text-text-secondary/60">No decisions need review</div>
          </div>
        ) : (
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {visibleItems.slice(0, 10).map((item) => (
              <ActionItemRow
                key={item.id}
                item={item}
                onDismiss={() => handleDismiss(item.id)}
                onClick={() => handleClick(item.id)}
              />
            ))}
            {visibleItems.length > 10 && (
              <div className="text-xs text-text-secondary/60 text-center py-2">
                +{visibleItems.length - 10} more
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
