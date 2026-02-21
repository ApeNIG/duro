import { useQuery } from '@tanstack/react-query'
import {
  Lightbulb,
  Loader2,
  AlertCircle,
  Clock,
  TrendingUp,
  CheckCircle,
  FileText,
  Scale,
  ArrowRight,
  RefreshCw,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

interface ActionItem {
  type: string
  id: string
  title: string
  age_days: number
  priority: 'low' | 'medium' | 'high'
}

interface InsightsData {
  summary: {
    total_facts: number
    total_decisions: number
    pending_review: number
    oldest_unreviewed_days: number
    recent_24h: number
  }
  action_items: ActionItem[]
  timestamp: string
}

const priorityStyles = {
  high: 'bg-red-500/10 border-red-500/30 text-red-400',
  medium: 'bg-warning/10 border-warning/30 text-warning',
  low: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
}

function StatCard({
  icon,
  label,
  value,
  subtext,
  color = 'text-text-primary',
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  subtext?: string
  color?: string
}) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-white/5">{icon}</div>
        <div>
          <div className="text-xs text-text-secondary uppercase">{label}</div>
          <div className={`text-2xl font-mono ${color}`}>{value}</div>
          {subtext && (
            <div className="text-xs text-text-secondary">{subtext}</div>
          )}
        </div>
      </div>
    </div>
  )
}

function ActionItemCard({
  item,
  onClick,
}: {
  item: ActionItem
  onClick: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-lg border cursor-pointer transition-all hover:scale-[1.01] ${priorityStyles[item.priority]}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Scale className="w-4 h-4" />
            <span className="text-xs uppercase font-medium">
              {item.priority} priority
            </span>
          </div>
          <h3 className="text-sm font-medium text-text-primary truncate">
            {item.title}
          </h3>
          <div className="flex items-center gap-2 mt-1 text-xs text-text-secondary">
            <Clock className="w-3 h-3" />
            {item.age_days} days old
          </div>
        </div>
        <ArrowRight className="w-4 h-4 flex-shrink-0" />
      </div>
    </div>
  )
}

export default function Insights() {
  const navigate = useNavigate()

  const { data, isLoading, refetch, isFetching } = useQuery<InsightsData>({
    queryKey: ['insights'],
    queryFn: async () => {
      const res = await fetch('/api/insights')
      if (!res.ok) throw new Error('Failed to fetch insights')
      return res.json()
    },
    refetchInterval: 60000, // Refresh every minute
  })

  const summary = data?.summary
  const actionItems = data?.action_items || []

  const highPriorityCount = actionItems.filter((i) => i.priority === 'high').length
  const mediumPriorityCount = actionItems.filter((i) => i.priority === 'medium').length

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Lightbulb className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-display font-semibold">Proactive Insights</h1>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center flex-1">
          <Loader2 className="w-6 h-6 animate-spin text-text-secondary" />
        </div>
      ) : (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-5 gap-4 mb-6">
            <StatCard
              icon={<FileText className="w-4 h-4 text-blue-400" />}
              label="Total Facts"
              value={summary?.total_facts || 0}
            />
            <StatCard
              icon={<Scale className="w-4 h-4 text-purple-400" />}
              label="Decisions"
              value={summary?.total_decisions || 0}
            />
            <StatCard
              icon={<AlertCircle className="w-4 h-4 text-warning" />}
              label="Pending Review"
              value={summary?.pending_review || 0}
              color={
                (summary?.pending_review || 0) > 10
                  ? 'text-warning'
                  : 'text-text-primary'
              }
            />
            <StatCard
              icon={<Clock className="w-4 h-4 text-red-400" />}
              label="Oldest Unreviewed"
              value={`${summary?.oldest_unreviewed_days || 0}d`}
              color={
                (summary?.oldest_unreviewed_days || 0) > 30
                  ? 'text-red-400'
                  : 'text-text-primary'
              }
            />
            <StatCard
              icon={<TrendingUp className="w-4 h-4 text-accent" />}
              label="Last 24h"
              value={summary?.recent_24h || 0}
              subtext="new artifacts"
            />
          </div>

          {/* Health Alerts */}
          {(highPriorityCount > 0 || (summary?.oldest_unreviewed_days || 0) > 30) && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-6">
              <div className="flex items-center gap-2 text-red-400 mb-2">
                <AlertCircle className="w-4 h-4" />
                <strong className="text-sm">Attention Required</strong>
              </div>
              <ul className="text-sm text-text-primary space-y-1">
                {highPriorityCount > 0 && (
                  <li>
                    • {highPriorityCount} decision{highPriorityCount > 1 ? 's' : ''} older
                    than 30 days without review
                  </li>
                )}
                {(summary?.oldest_unreviewed_days || 0) > 60 && (
                  <li>
                    • Oldest unreviewed decision is {summary?.oldest_unreviewed_days} days
                    old - decision drift risk
                  </li>
                )}
              </ul>
              <button
                onClick={() => navigate('/reviews')}
                className="mt-3 flex items-center gap-2 text-sm text-red-400 hover:underline"
              >
                Go to Reviews <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          )}

          {/* Action Items */}
          <div className="flex-1 overflow-auto min-h-0">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-text-primary">
                Decisions Needing Review
              </h2>
              <div className="flex items-center gap-3 text-xs">
                {highPriorityCount > 0 && (
                  <span className="text-red-400">{highPriorityCount} high</span>
                )}
                {mediumPriorityCount > 0 && (
                  <span className="text-warning">{mediumPriorityCount} medium</span>
                )}
              </div>
            </div>

            {actionItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <CheckCircle className="w-12 h-12 text-accent mb-3" />
                <h3 className="text-lg font-medium text-text-primary mb-1">
                  All caught up!
                </h3>
                <p className="text-sm text-text-secondary">
                  No decisions need review at this time.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {actionItems.map((item) => (
                  <ActionItemCard
                    key={item.id}
                    item={item}
                    onClick={() => navigate(`/reviews?decision=${item.id}`)}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
