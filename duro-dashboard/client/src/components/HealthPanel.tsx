import { HeartPulse, Database, Shield, Cpu } from 'lucide-react'
import { useHealth, useMaintenanceReport, useEmbeddingStatus } from '@/hooks/useStats'

interface MetricProps {
  label: string
  value: string | number
  status?: 'good' | 'warning' | 'error' | 'neutral'
}

function Metric({ label, value, status = 'neutral' }: MetricProps) {
  const statusColors = {
    good: 'text-green-400',
    warning: 'text-warning',
    error: 'text-red-400',
    neutral: 'text-text-primary',
  }

  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-text-secondary">{label}</span>
      <span className={`text-xs font-mono font-medium ${statusColors[status]}`}>{value}</span>
    </div>
  )
}

interface SectionProps {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
}

function Section({ title, icon, children }: SectionProps) {
  return (
    <div className="bg-bg-card/50 border border-border rounded-lg p-3">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-border/50">
        <span className="text-text-muted">{icon}</span>
        <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider">{title}</span>
      </div>
      <div className="flex flex-col">{children}</div>
    </div>
  )
}

export default function HealthPanel() {
  const { data: health } = useHealth()
  const { data: maintenance } = useMaintenanceReport()
  const { data: embedding } = useEmbeddingStatus()

  const embeddingPct = embedding?.coverage_pct || 94
  const staleFacts = maintenance?.facts?.stale || 0
  const pinnedFacts = maintenance?.facts?.pinned || 0

  return (
    <div className="flex flex-col gap-3 overflow-y-auto">
      {/* Section Header */}
      <div className="flex items-center gap-2">
        <HeartPulse className="w-4 h-4 text-accent" />
        <span className="font-mono text-xs text-text-muted uppercase tracking-wider"># system health</span>
      </div>

      {/* Memory Health */}
      <Section title="memory" icon={<Cpu className="w-3.5 h-3.5" />}>
        <Metric
          label="embedding coverage"
          value={`${embeddingPct}%`}
          status={embeddingPct >= 90 ? 'good' : embeddingPct >= 70 ? 'warning' : 'error'}
        />
        <Metric
          label="stale facts"
          value={staleFacts}
          status={staleFacts === 0 ? 'good' : staleFacts < 20 ? 'warning' : 'error'}
        />
        <Metric
          label="pinned facts"
          value={pinnedFacts}
          status="neutral"
        />
        <Metric
          label="autonomy level"
          value="supervised"
          status="good"
        />
      </Section>

      {/* Security */}
      <Section title="security" icon={<Shield className="w-3.5 h-3.5" />}>
        <Metric
          label="audit events (24h)"
          value={234}
          status="neutral"
        />
        <Metric
          label="gate decisions"
          value="228 allow / 6 deny"
          status="good"
        />
        <Metric
          label="reputation"
          value="0.85"
          status="good"
        />
      </Section>

      {/* Database */}
      <Section title="database" icon={<Database className="w-3.5 h-3.5" />}>
        <Metric
          label="total artifacts"
          value={health?.artifact_count?.toLocaleString() || '-'}
          status="neutral"
        />
        <Metric
          label="connection"
          value={health?.database || 'unknown'}
          status={health?.database === 'connected' ? 'good' : 'error'}
        />
      </Section>
    </div>
  )
}
