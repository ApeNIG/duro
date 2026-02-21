import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Play,
  CheckCircle,
  XCircle,
  Clock,
  ChevronRight,
  Loader2,
  Target,
  ListChecks,
  Zap,
  Award,
  AlertCircle,
  LayoutGrid,
  GitCommit,
} from 'lucide-react'

interface Episode {
  id: string
  created_at: string
  title: string | null
  tags: string[]
  goal?: string
  plan?: string[]
  actions?: Array<{
    summary: string
    tool?: string
    run_id?: string
    timestamp?: string
  }>
  result?: 'success' | 'partial' | 'failed'
  result_summary?: string
  status?: 'open' | 'closed'
  duration_mins?: number
  links?: {
    facts_created?: string[]
    decisions_used?: string[]
    decisions_created?: string[]
    skills_used?: string[]
  }
  evaluation?: {
    grade: string
    rubric: Record<string, { score: number; notes?: string }>
    next_change?: string
  }
}

interface EpisodesResponse {
  episodes: Episode[]
  total: number
  has_more: boolean
}

const resultColors = {
  success: 'text-green-400 bg-green-500/10 border-green-500/30',
  partial: 'text-warning bg-warning/10 border-warning/30',
  failed: 'text-red-400 bg-red-500/10 border-red-500/30',
}

const resultIcons = {
  success: CheckCircle,
  partial: AlertCircle,
  failed: XCircle,
}

function formatDuration(mins: number | undefined): string {
  if (!mins) return '-'
  if (mins < 1) return '<1 min'
  if (mins < 60) return `${Math.round(mins)} min`
  const hours = Math.floor(mins / 60)
  const remaining = Math.round(mins % 60)
  return `${hours}h ${remaining}m`
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

function TimelineNode({ episode, isLast }: { episode: Episode; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const isOpen = episode.status === 'open'
  const result = episode.result || 'pending'
  const ResultIcon = resultIcons[result as keyof typeof resultIcons] || Clock

  return (
    <div className="flex gap-4">
      {/* Timeline Line */}
      <div className="flex flex-col items-center">
        <div
          className={`w-10 h-10 rounded-full flex items-center justify-center border-2 ${
            isOpen
              ? 'border-accent bg-accent/20'
              : result === 'success'
              ? 'border-green-400 bg-green-500/20'
              : result === 'failed'
              ? 'border-red-400 bg-red-500/20'
              : 'border-warning bg-warning/20'
          }`}
        >
          {isOpen ? (
            <Play className="w-4 h-4 text-accent" />
          ) : (
            <ResultIcon
              className={`w-4 h-4 ${
                result === 'success'
                  ? 'text-green-400'
                  : result === 'failed'
                  ? 'text-red-400'
                  : 'text-warning'
              }`}
            />
          )}
        </div>
        {!isLast && <div className="w-0.5 flex-1 bg-border mt-2" />}
      </div>

      {/* Content */}
      <div className="flex-1 pb-6">
        <div
          className="bg-card border border-border rounded-lg p-4 hover:border-accent/30 transition-colors cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          {/* Header */}
          <div className="flex items-center gap-2 mb-2 text-xs">
            <span
              className={`px-2 py-0.5 rounded ${
                isOpen
                  ? 'bg-accent/20 text-accent'
                  : resultColors[result as keyof typeof resultColors] || ''
              }`}
            >
              {isOpen ? 'in progress' : result}
            </span>
            {episode.duration_mins && (
              <span className="text-text-secondary flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatDuration(episode.duration_mins)}
              </span>
            )}
            {episode.evaluation?.grade && (
              <span className="px-2 py-0.5 bg-accent/10 text-accent rounded">
                {episode.evaluation.grade}
              </span>
            )}
            <span className="text-text-secondary ml-auto">
              {formatDate(episode.created_at)}
            </span>
          </div>

          {/* Goal */}
          <h3 className="text-sm text-text-primary font-medium mb-1">
            {episode.goal || episode.title || episode.id}
          </h3>

          {episode.result_summary && (
            <p className="text-xs text-text-secondary line-clamp-2 mb-2">
              {episode.result_summary}
            </p>
          )}

          {/* Actions preview */}
          {episode.actions && episode.actions.length > 0 && (
            <div className="flex items-center gap-1 text-xs text-text-secondary">
              <GitCommit className="w-3 h-3" />
              {episode.actions.length} action{episode.actions.length > 1 ? 's' : ''}
              <ChevronRight
                className={`w-3 h-3 ml-auto transition-transform ${expanded ? 'rotate-90' : ''}`}
              />
            </div>
          )}
        </div>

        {/* Expanded Actions */}
        {expanded && episode.actions && episode.actions.length > 0 && (
          <div className="mt-2 ml-4 space-y-1">
            {episode.actions.map((action, i) => (
              <div
                key={i}
                className="flex items-start gap-2 text-xs border-l-2 border-accent/30 pl-3 py-1"
              >
                <div className="w-5 h-5 rounded-full bg-accent/10 text-accent flex items-center justify-center flex-shrink-0 text-[10px]">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-text-primary">{action.summary}</span>
                  {action.tool && (
                    <span className="text-text-secondary ml-1">via {action.tool}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function EpisodeCard({ episode }: { episode: Episode }) {
  const [expanded, setExpanded] = useState(false)
  const isOpen = episode.status === 'open'
  const result = episode.result || 'pending'
  const ResultIcon = resultIcons[result as keyof typeof resultIcons] || Clock

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className="p-4 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-3">
          {/* Status Icon */}
          <div className="mt-0.5">
            {isOpen ? (
              <Play className="w-5 h-5 text-accent animate-pulse" />
            ) : (
              <ResultIcon
                className={`w-5 h-5 ${
                  result === 'success'
                    ? 'text-green-400'
                    : result === 'partial'
                    ? 'text-warning'
                    : result === 'failed'
                    ? 'text-red-400'
                    : 'text-text-secondary'
                }`}
              />
            )}
          </div>

          <div className="flex-1 min-w-0">
            {/* Status badges */}
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              {isOpen ? (
                <span className="text-xs px-2 py-0.5 rounded border text-accent bg-accent/10 border-accent/30">
                  in progress
                </span>
              ) : (
                <span
                  className={`text-xs px-2 py-0.5 rounded border ${
                    resultColors[result as keyof typeof resultColors] || ''
                  }`}
                >
                  {result}
                </span>
              )}
              {episode.duration_mins && (
                <span className="text-xs text-text-secondary flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatDuration(episode.duration_mins)}
                </span>
              )}
              {episode.evaluation?.grade && (
                <span className="text-xs px-2 py-0.5 bg-accent/10 text-accent rounded">
                  {episode.evaluation.grade}
                </span>
              )}
              <span className="text-xs text-text-secondary">
                {formatDate(episode.created_at)}
              </span>
            </div>

            {/* Goal */}
            <h3 className="text-sm text-text-primary font-medium mb-1">
              {episode.goal || episode.title || episode.id}
            </h3>

            {/* Result summary */}
            {episode.result_summary && (
              <p className="text-xs text-text-secondary line-clamp-2">
                {episode.result_summary}
              </p>
            )}

            {/* Actions count */}
            {episode.actions && episode.actions.length > 0 && (
              <div className="flex items-center gap-2 mt-2 text-xs text-text-secondary">
                <Zap className="w-3 h-3" />
                {episode.actions.length} actions
                {episode.links?.skills_used && episode.links.skills_used.length > 0 && (
                  <>
                    <span className="text-text-secondary/50">•</span>
                    {episode.links.skills_used.length} skills used
                  </>
                )}
              </div>
            )}

            {/* Tags */}
            {episode.tags && episode.tags.length > 0 && (
              <div className="flex gap-1 mt-2 flex-wrap">
                {episode.tags.slice(0, 4).map((tag) => (
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
        <div className="border-t border-border p-4 bg-page/50 space-y-4">
          {/* Plan */}
          {episode.plan && episode.plan.length > 0 && (
            <div>
              <div className="flex items-center gap-2 text-xs text-text-secondary uppercase mb-2">
                <ListChecks className="w-3.5 h-3.5" />
                Plan
              </div>
              <ol className="text-sm text-text-primary space-y-1 list-decimal list-inside">
                {episode.plan.map((step, i) => (
                  <li key={i} className="text-text-secondary">
                    <span className="text-text-primary">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Actions Timeline */}
          {episode.actions && episode.actions.length > 0 && (
            <div>
              <div className="flex items-center gap-2 text-xs text-text-secondary uppercase mb-2">
                <Zap className="w-3.5 h-3.5" />
                Actions
              </div>
              <div className="space-y-2">
                {episode.actions.map((action, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 text-sm border-l-2 border-border pl-3 py-1"
                  >
                    <div className="w-5 h-5 rounded-full bg-accent/20 text-accent text-xs flex items-center justify-center flex-shrink-0 mt-0.5">
                      {i + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-text-primary">{action.summary}</p>
                      {action.tool && (
                        <span className="text-xs text-text-secondary">
                          via {action.tool}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evaluation */}
          {episode.evaluation && (
            <div>
              <div className="flex items-center gap-2 text-xs text-text-secondary uppercase mb-2">
                <Award className="w-3.5 h-3.5" />
                Evaluation
              </div>
              <div className="bg-card border border-border rounded p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Grade</span>
                  <span className="text-lg font-bold text-accent">
                    {episode.evaluation.grade}
                  </span>
                </div>
                {episode.evaluation.rubric && (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {Object.entries(episode.evaluation.rubric).map(([key, val]) => (
                      <div key={key} className="flex justify-between">
                        <span className="text-text-secondary capitalize">
                          {key.replace(/_/g, ' ')}
                        </span>
                        <span className="text-text-primary">{val.score}/5</span>
                      </div>
                    ))}
                  </div>
                )}
                {episode.evaluation.next_change && (
                  <div className="text-xs text-warning border-t border-border pt-2 mt-2">
                    <strong>Next time:</strong> {episode.evaluation.next_change}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Links */}
          {episode.links && Object.keys(episode.links).length > 0 && (
            <div className="flex flex-wrap gap-2 text-xs">
              {episode.links.facts_created && episode.links.facts_created.length > 0 && (
                <span className="px-2 py-1 bg-blue-500/10 text-blue-400 rounded">
                  {episode.links.facts_created.length} facts created
                </span>
              )}
              {episode.links.decisions_created && episode.links.decisions_created.length > 0 && (
                <span className="px-2 py-1 bg-purple-500/10 text-purple-400 rounded">
                  {episode.links.decisions_created.length} decisions made
                </span>
              )}
              {episode.links.skills_used && episode.links.skills_used.length > 0 && (
                <span className="px-2 py-1 bg-green-500/10 text-green-400 rounded">
                  {episode.links.skills_used.length} skills used
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Episodes() {
  const [filter, setFilter] = useState<'all' | 'open' | 'closed'>('all')
  const [viewMode, setViewMode] = useState<'cards' | 'timeline'>('timeline')

  const { data, isLoading } = useQuery<EpisodesResponse>({
    queryKey: ['episodes'],
    queryFn: async () => {
      const res = await fetch('/api/episodes?limit=100')
      if (!res.ok) throw new Error('Failed to fetch episodes')
      return res.json()
    },
    refetchInterval: 15000,
  })

  const { data: stats } = useQuery({
    queryKey: ['episode-stats'],
    queryFn: async () => {
      const res = await fetch('/api/episodes/stats/summary')
      if (!res.ok) throw new Error('Failed to fetch stats')
      return res.json()
    },
  })

  const episodes = data?.episodes || []
  const filteredEpisodes =
    filter === 'all'
      ? episodes
      : episodes.filter((e) => e.status === filter)

  const openCount = episodes.filter((e) => e.status === 'open').length
  const successCount = episodes.filter((e) => e.result === 'success').length
  const failedCount = episodes.filter((e) => e.result === 'failed').length

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Target className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-display font-semibold">Episode Timeline</h1>
          {openCount > 0 && (
            <span className="px-2 py-0.5 bg-accent/20 text-accent text-xs rounded-full animate-pulse">
              {openCount} in progress
            </span>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4">
          {/* View Toggle */}
          <div className="flex items-center gap-1 bg-card border border-border rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('cards')}
              className={`p-1.5 rounded transition-colors ${
                viewMode === 'cards'
                  ? 'bg-accent text-page'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
              title="Card view"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('timeline')}
              className={`p-1.5 rounded transition-colors ${
                viewMode === 'timeline'
                  ? 'bg-accent text-page'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
              title="Timeline view"
            >
              <GitCommit className="w-4 h-4" />
            </button>
          </div>

          {/* Filter */}
          <div className="flex items-center gap-2">
            {(['all', 'open', 'closed'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 text-sm rounded transition-colors capitalize ${
                  filter === f
                    ? 'bg-accent text-page'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-6">
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Total</div>
          <div className="text-2xl font-mono text-text-primary">{stats?.total || episodes.length}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Success Rate</div>
          <div className="text-2xl font-mono text-green-400">
            {stats?.by_result?.success && stats?.total
              ? Math.round((stats.by_result.success / stats.total) * 100)
              : successCount && episodes.length
              ? Math.round((successCount / episodes.filter(e => e.result).length) * 100)
              : 0}%
          </div>
        </div>
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Failed</div>
          <div className="text-2xl font-mono text-red-400">{stats?.by_result?.failed || failedCount}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Avg Duration</div>
          <div className="text-2xl font-mono text-text-primary">
            {stats?.avg_duration_mins ? formatDuration(stats.avg_duration_mins) : '-'}
          </div>
        </div>
      </div>

      {/* Episode List */}
      <div className="flex-1 overflow-auto min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-text-secondary" />
          </div>
        ) : filteredEpisodes.length === 0 ? (
          <div className="text-center py-12 text-text-secondary">
            No episodes found
          </div>
        ) : viewMode === 'timeline' ? (
          <div className="pl-2">
            {filteredEpisodes.map((episode, index) => (
              <TimelineNode
                key={episode.id}
                episode={episode}
                isLast={index === filteredEpisodes.length - 1}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredEpisodes.map((episode) => (
              <EpisodeCard key={episode.id} episode={episode} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
