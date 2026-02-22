import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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
  AlertTriangle,
  Sparkles,
  RotateCcw,
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

interface StaleFact {
  id: string
  title: string
  claim: string
  confidence: number
  importance: number
  age_days: number
  days_since_reinforcement: number
  reinforcement_count: number
  staleness_score: number
  tags: string[]
}

interface StaleDecision {
  id: string
  title: string
  decision: string
  age_days: number
  days_since_validation: number
  validation_count: number
  outcome_status: string | null
  staleness_score: number
  tags: string[]
}

interface StaleKnowledgeData {
  stale_facts: StaleFact[]
  stale_decisions: StaleDecision[]
  stats: {
    total_stale: number
    stale_facts_count: number
    stale_decisions_count: number
    avg_fact_staleness: number
    avg_decision_staleness: number
  }
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

function StaleFactCard({
  fact,
  onReinforce,
  isReinforcing,
}: {
  fact: StaleFact
  onReinforce: (id: string) => void
  isReinforcing: boolean
}) {
  const getStalenessColor = (score: number) => {
    if (score > 2) return 'text-red-400 bg-red-500/20'
    if (score > 1) return 'text-warning bg-warning/20'
    return 'text-blue-400 bg-blue-500/20'
  }

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-start gap-3">
        {/* Staleness Badge */}
        <div className={`flex flex-col items-center justify-center w-12 h-12 rounded-lg ${getStalenessColor(fact.staleness_score)}`}>
          <span className="text-lg font-bold">{fact.staleness_score}</span>
          <span className="text-[10px] uppercase">stale</span>
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-text-primary line-clamp-2 mb-1">
            {fact.title}
          </h3>
          <div className="flex items-center gap-3 text-xs text-text-secondary">
            <span>{fact.age_days}d old</span>
            <span>{fact.days_since_reinforcement}d since reinforced</span>
            <span>{Math.round(fact.confidence * 100)}% conf</span>
          </div>
          {fact.tags.length > 0 && (
            <div className="flex gap-1 mt-2">
              {fact.tags.map((tag) => (
                <span key={tag} className="text-xs px-1.5 py-0.5 bg-white/5 rounded text-text-secondary">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={() => onReinforce(fact.id)}
          disabled={isReinforcing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-accent/20 text-accent border border-accent/30 rounded hover:bg-accent/30 transition-colors disabled:opacity-50"
        >
          {isReinforcing ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <RotateCcw className="w-3 h-3" />
          )}
          Reinforce
        </button>
      </div>
    </div>
  )
}

function StaleDecisionCard({
  decision,
  onClick,
}: {
  decision: StaleDecision
  onClick: () => void
}) {
  const getStalenessColor = (score: number) => {
    if (score > 2) return 'text-red-400 bg-red-500/20'
    if (score > 1) return 'text-warning bg-warning/20'
    return 'text-blue-400 bg-blue-500/20'
  }

  return (
    <div
      onClick={onClick}
      className="bg-card border border-border rounded-lg p-4 cursor-pointer hover:border-accent/30 transition-colors"
    >
      <div className="flex items-start gap-3">
        {/* Staleness Badge */}
        <div className={`flex flex-col items-center justify-center w-12 h-12 rounded-lg ${getStalenessColor(decision.staleness_score)}`}>
          <span className="text-lg font-bold">{decision.staleness_score}</span>
          <span className="text-[10px] uppercase">stale</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {!decision.outcome_status || decision.outcome_status === 'pending' ? (
              <span className="text-xs px-1.5 py-0.5 bg-warning/20 text-warning rounded">unvalidated</span>
            ) : (
              <span className="text-xs px-1.5 py-0.5 bg-accent/20 text-accent rounded">{decision.outcome_status}</span>
            )}
          </div>
          <h3 className="text-sm font-medium text-text-primary line-clamp-2 mb-1">
            {decision.title}
          </h3>
          <div className="flex items-center gap-3 text-xs text-text-secondary">
            <span>{decision.age_days}d old</span>
            <span>{decision.days_since_validation}d since validated</span>
            <span>{decision.validation_count} validations</span>
          </div>
        </div>

        <ArrowRight className="w-4 h-4 text-text-secondary flex-shrink-0" />
      </div>
    </div>
  )
}

export default function Insights() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'reviews' | 'stale'>('reviews')
  const [reinforcingId, setReinforcingId] = useState<string | null>(null)

  const { data, isLoading, refetch, isFetching } = useQuery<InsightsData>({
    queryKey: ['insights'],
    queryFn: async () => {
      const res = await fetch('/api/insights')
      if (!res.ok) throw new Error('Failed to fetch insights')
      return res.json()
    },
    refetchInterval: 60000,
  })

  const { data: staleData, isLoading: staleLoading } = useQuery<StaleKnowledgeData>({
    queryKey: ['stale-knowledge'],
    queryFn: async () => {
      const res = await fetch('/api/insights/stale?min_age_days=7&min_importance=0.3&limit=30')
      if (!res.ok) throw new Error('Failed to fetch stale knowledge')
      return res.json()
    },
    refetchInterval: 60000,
  })

  const reinforceMutation = useMutation({
    mutationFn: async (factId: string) => {
      setReinforcingId(factId)
      const res = await fetch(`/api/insights/reinforce/${factId}`, { method: 'POST' })
      if (!res.ok) throw new Error('Failed to reinforce fact')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stale-knowledge'] })
      setReinforcingId(null)
    },
    onError: () => {
      setReinforcingId(null)
    },
  })

  const summary = data?.summary
  const actionItems = data?.action_items || []
  const staleFacts = staleData?.stale_facts || []
  const staleDecisions = staleData?.stale_decisions || []

  const highPriorityCount = actionItems.filter((i) => i.priority === 'high').length
  const mediumPriorityCount = actionItems.filter((i) => i.priority === 'medium').length
  const totalStale = (staleData?.stats.total_stale || 0)

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
              icon={<AlertTriangle className="w-4 h-4 text-orange-400" />}
              label="Stale Knowledge"
              value={totalStale}
              color={totalStale > 20 ? 'text-orange-400' : 'text-text-primary'}
            />
            <StatCard
              icon={<TrendingUp className="w-4 h-4 text-accent" />}
              label="Last 24h"
              value={summary?.recent_24h || 0}
              subtext="new artifacts"
            />
          </div>

          {/* Health Alerts */}
          {(highPriorityCount > 0 || (summary?.oldest_unreviewed_days || 0) > 30 || totalStale > 20) && (
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
                {totalStale > 20 && (
                  <li>
                    • {totalStale} stale facts/decisions need reinforcement or validation
                  </li>
                )}
              </ul>
            </div>
          )}

          {/* Tab Navigation */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setActiveTab('reviews')}
              className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-colors ${
                activeTab === 'reviews'
                  ? 'bg-accent/20 text-accent border border-accent/30'
                  : 'bg-white/5 text-text-secondary hover:text-text-primary'
              }`}
            >
              <CheckCircle className="w-4 h-4" />
              Pending Reviews
              {actionItems.length > 0 && (
                <span className="px-1.5 py-0.5 text-xs bg-warning/20 text-warning rounded-full">
                  {actionItems.length}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('stale')}
              className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-colors ${
                activeTab === 'stale'
                  ? 'bg-accent/20 text-accent border border-accent/30'
                  : 'bg-white/5 text-text-secondary hover:text-text-primary'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              Stale Knowledge
              {totalStale > 0 && (
                <span className="px-1.5 py-0.5 text-xs bg-orange-500/20 text-orange-400 rounded-full">
                  {totalStale}
                </span>
              )}
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-auto min-h-0">
            {activeTab === 'reviews' ? (
              <>
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
              </>
            ) : (
              <>
                {staleLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin text-text-secondary" />
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Stale Facts */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h2 className="text-sm font-medium text-text-primary flex items-center gap-2">
                          <FileText className="w-4 h-4 text-amber-400" />
                          Stale Facts
                          <span className="text-xs text-text-secondary">({staleFacts.length})</span>
                        </h2>
                      </div>

                      {staleFacts.length === 0 ? (
                        <div className="text-center py-8 text-text-secondary text-sm">
                          No stale facts found. Your knowledge is fresh!
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {staleFacts.map((fact) => (
                            <StaleFactCard
                              key={fact.id}
                              fact={fact}
                              onReinforce={(id) => reinforceMutation.mutate(id)}
                              isReinforcing={reinforcingId === fact.id}
                            />
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Stale Decisions */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h2 className="text-sm font-medium text-text-primary flex items-center gap-2">
                          <Scale className="w-4 h-4 text-purple-400" />
                          Stale Decisions
                          <span className="text-xs text-text-secondary">({staleDecisions.length})</span>
                        </h2>
                      </div>

                      {staleDecisions.length === 0 ? (
                        <div className="text-center py-8 text-text-secondary text-sm">
                          No stale decisions found. All decisions are validated!
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {staleDecisions.map((decision) => (
                            <StaleDecisionCard
                              key={decision.id}
                              decision={decision}
                              onClick={() => navigate(`/reviews?decision=${decision.id}`)}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
