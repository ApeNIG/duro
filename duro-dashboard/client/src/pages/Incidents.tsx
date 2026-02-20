import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  Loader2,
  ChevronRight,
  Bug,
  Shield,
  Lightbulb,
  AlertCircle,
  CheckCircle,
  TrendingUp,
} from 'lucide-react'

interface Incident {
  id: string
  created_at: string
  title: string | null
  tags: string[]
  symptom?: string
  actual_cause?: string
  fix?: string
  prevention?: string
  severity?: 'low' | 'medium' | 'high' | 'critical'
  repro_steps?: string[]
  first_bad_boundary?: string
  why_not_caught?: string
  content?: Record<string, unknown>
}

interface IncidentsResponse {
  incidents: Incident[]
  total: number
  has_more: boolean
}

interface IncidentStats {
  total: number
  by_severity: Record<string, number>
  common_boundaries: Array<{ boundary: string; count: number }>
  common_tags: Array<{ tag: string; count: number }>
  recent_causes: string[]
}

interface IncidentPatterns {
  recurring_boundaries: Array<{ boundary: string; occurrences: number }>
  preventions_implemented: string[]
  detection_gaps: string[]
  pattern_summary: {
    total_incidents: number
    unique_boundaries: number
    has_recurring_patterns: boolean
  }
}

const severityColors = {
  low: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  medium: 'text-warning bg-warning/10 border-warning/30',
  high: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  critical: 'text-red-400 bg-red-500/10 border-red-500/30',
}

const severityIcons = {
  low: AlertCircle,
  medium: AlertTriangle,
  high: AlertTriangle,
  critical: Bug,
}

function formatDate(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function IncidentCard({ incident }: { incident: Incident }) {
  const [expanded, setExpanded] = useState(false)
  const severity = incident.severity || 'medium'
  const SeverityIcon = severityIcons[severity] || AlertTriangle

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className="p-4 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-3">
          {/* Severity Icon */}
          <div className="mt-0.5">
            <SeverityIcon
              className={`w-5 h-5 ${
                severity === 'critical'
                  ? 'text-red-400'
                  : severity === 'high'
                  ? 'text-orange-400'
                  : severity === 'medium'
                  ? 'text-warning'
                  : 'text-blue-400'
              }`}
            />
          </div>

          <div className="flex-1 min-w-0">
            {/* Header badges */}
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span
                className={`text-xs px-2 py-0.5 rounded border uppercase ${severityColors[severity]}`}
              >
                {severity}
              </span>
              <span className="text-xs text-text-secondary">
                {formatDate(incident.created_at)}
              </span>
            </div>

            {/* Symptom */}
            <h3 className="text-sm text-text-primary font-medium mb-1">
              {incident.symptom || incident.title || incident.id}
            </h3>

            {/* Cause preview */}
            {incident.actual_cause && (
              <p className="text-xs text-text-secondary line-clamp-2">
                <strong>Cause:</strong> {incident.actual_cause}
              </p>
            )}

            {/* Boundary */}
            {incident.first_bad_boundary && (
              <div className="flex items-center gap-1 mt-2 text-xs text-orange-400">
                <AlertCircle className="w-3 h-3" />
                {incident.first_bad_boundary}
              </div>
            )}

            {/* Tags */}
            {incident.tags && incident.tags.length > 0 && (
              <div className="flex gap-1 mt-2 flex-wrap">
                {incident.tags.slice(0, 4).map((tag) => (
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

      {/* Expanded RCA */}
      {expanded && (
        <div className="border-t border-border p-4 bg-page/50 space-y-4">
          {/* Repro Steps */}
          {incident.repro_steps && incident.repro_steps.length > 0 && (
            <div>
              <div className="flex items-center gap-2 text-xs text-text-secondary uppercase mb-2">
                <Bug className="w-3.5 h-3.5" />
                Reproduction Steps
              </div>
              <ol className="text-sm text-text-primary space-y-1 list-decimal list-inside">
                {incident.repro_steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          )}

          {/* Root Cause */}
          {incident.actual_cause && (
            <div>
              <div className="flex items-center gap-2 text-xs text-text-secondary uppercase mb-2">
                <AlertTriangle className="w-3.5 h-3.5" />
                Root Cause
              </div>
              <p className="text-sm text-text-primary bg-red-500/10 border border-red-500/20 rounded p-3">
                {incident.actual_cause}
              </p>
            </div>
          )}

          {/* Fix */}
          {incident.fix && (
            <div>
              <div className="flex items-center gap-2 text-xs text-text-secondary uppercase mb-2">
                <CheckCircle className="w-3.5 h-3.5" />
                Fix Applied
              </div>
              <p className="text-sm text-text-primary bg-green-500/10 border border-green-500/20 rounded p-3">
                {incident.fix}
              </p>
            </div>
          )}

          {/* Prevention */}
          {incident.prevention && (
            <div>
              <div className="flex items-center gap-2 text-xs text-text-secondary uppercase mb-2">
                <Shield className="w-3.5 h-3.5" />
                Prevention
              </div>
              <p className="text-sm text-text-primary bg-accent/10 border border-accent/20 rounded p-3">
                {incident.prevention}
              </p>
            </div>
          )}

          {/* Why Not Caught */}
          {incident.why_not_caught && (
            <div>
              <div className="flex items-center gap-2 text-xs text-text-secondary uppercase mb-2">
                <Lightbulb className="w-3.5 h-3.5" />
                Why Not Caught Earlier
              </div>
              <p className="text-sm text-warning">
                {incident.why_not_caught}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Incidents() {
  const [severityFilter, setSeverityFilter] = useState<string>('all')

  const { data, isLoading } = useQuery<IncidentsResponse>({
    queryKey: ['incidents'],
    queryFn: async () => {
      const res = await fetch('/api/incidents?limit=100')
      if (!res.ok) throw new Error('Failed to fetch incidents')
      return res.json()
    },
    refetchInterval: 30000,
  })

  const { data: stats } = useQuery<IncidentStats>({
    queryKey: ['incident-stats'],
    queryFn: async () => {
      const res = await fetch('/api/incidents/stats/summary')
      if (!res.ok) throw new Error('Failed to fetch stats')
      return res.json()
    },
  })

  const { data: patterns } = useQuery<IncidentPatterns>({
    queryKey: ['incident-patterns'],
    queryFn: async () => {
      const res = await fetch('/api/incidents/patterns')
      if (!res.ok) throw new Error('Failed to fetch patterns')
      return res.json()
    },
  })

  const incidents = data?.incidents || []
  const filteredIncidents =
    severityFilter === 'all'
      ? incidents
      : incidents.filter((i) => i.severity === severityFilter)

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-display font-semibold">Incident Dashboard</h1>
          <span className="text-sm text-text-secondary">
            {incidents.length} incidents
          </span>
        </div>

        {/* Filter */}
        <div className="flex items-center gap-2">
          {(['all', 'critical', 'high', 'medium', 'low'] as const).map((sev) => (
            <button
              key={sev}
              onClick={() => setSeverityFilter(sev)}
              className={`px-3 py-1.5 text-sm rounded transition-colors capitalize ${
                severityFilter === sev
                  ? 'bg-accent text-page'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Total</div>
          <div className="text-2xl font-mono text-text-primary">
            {stats?.total || incidents.length}
          </div>
        </div>
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Critical</div>
          <div className="text-2xl font-mono text-red-400">
            {stats?.by_severity?.critical || 0}
          </div>
        </div>
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">High</div>
          <div className="text-2xl font-mono text-orange-400">
            {stats?.by_severity?.high || 0}
          </div>
        </div>
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Recurring</div>
          <div className="text-2xl font-mono text-warning">
            {patterns?.recurring_boundaries?.length || 0}
          </div>
        </div>
      </div>

      {/* Patterns Alert */}
      {patterns?.recurring_boundaries && patterns.recurring_boundaries.length > 0 && (
        <div className="bg-warning/10 border border-warning/30 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-2 text-warning mb-2">
            <TrendingUp className="w-4 h-4" />
            <strong className="text-sm">Recurring Patterns Detected</strong>
          </div>
          <div className="flex flex-wrap gap-2">
            {patterns.recurring_boundaries.map((p) => (
              <span
                key={p.boundary}
                className="text-xs px-2 py-1 bg-warning/20 text-warning rounded"
              >
                {p.boundary} ({p.occurrences}x)
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Common Boundaries */}
      {stats?.common_boundaries && stats.common_boundaries.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-4 mb-6">
          <div className="text-xs text-text-secondary uppercase mb-2">
            Common Failure Points
          </div>
          <div className="flex flex-wrap gap-2">
            {stats.common_boundaries.map((b) => (
              <span
                key={b.boundary}
                className="text-xs px-2 py-1 bg-orange-500/10 text-orange-400 border border-orange-500/20 rounded"
              >
                {b.boundary} ({b.count})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Incident List */}
      <div className="flex-1 overflow-auto min-h-0 space-y-3">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-text-secondary" />
          </div>
        ) : filteredIncidents.length === 0 ? (
          <div className="text-center py-12 text-text-secondary">
            <Shield className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No incidents found</p>
            <p className="text-xs mt-1">That's a good thing!</p>
          </div>
        ) : (
          filteredIncidents.map((incident) => (
            <IncidentCard key={incident.id} incident={incident} />
          ))
        )}
      </div>
    </div>
  )
}
