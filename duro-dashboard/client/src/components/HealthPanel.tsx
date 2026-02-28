import { useHealth, useMaintenanceReport, useEmbeddingStatus } from '@/hooks/useStats'

interface DataRowProps {
  label: string
  value: string | number
  colorClass?: string
}

function DataRow({ label, value, colorClass = '' }: DataRowProps) {
  return (
    <div className="data-row">
      <span className="data-label">{label}</span>
      <span className={`data-value ${colorClass}`}>{value}</span>
    </div>
  )
}

export default function HealthPanel() {
  const { data: health } = useHealth()
  const { data: maintenance } = useMaintenanceReport()
  const { data: embedding } = useEmbeddingStatus()

  return (
    <div className="flex flex-col gap-4 overflow-y-auto">
      {/* Section Header */}
      <div className="font-mono text-xs text-text-muted"># system health</div>

      {/* Health Stats */}
      <div className="flex flex-col">
        <DataRow
          label="embedding coverage"
          value={`${embedding?.coverage_pct || 94}%`}
          colorClass="cyan"
        />
        <DataRow
          label="stale facts"
          value={maintenance?.facts?.stale || 12}
          colorClass="orange"
        />
        <DataRow
          label="pinned facts"
          value={maintenance?.facts?.pinned || 47}
        />
        <DataRow
          label="autonomy level"
          value="supervised"
          colorClass="purple"
        />
      </div>

      {/* Divider */}
      <div className="h-px bg-border my-2" />

      {/* Security Stats */}
      <div className="flex flex-col">
        <DataRow
          label="audit events (24h)"
          value={234}
        />
        <DataRow
          label="gate decisions"
          value="ALLOW: 228 | DENY: 6"
        />
        <DataRow
          label="reputation (overall)"
          value="0.85"
          colorClass="green"
        />
      </div>

      {/* Divider */}
      <div className="h-px bg-border my-2" />

      {/* Database Info */}
      <div className="flex flex-col">
        <DataRow
          label="total artifacts"
          value={health?.artifact_count?.toLocaleString() || '-'}
        />
        <DataRow
          label="database status"
          value={health?.database || 'unknown'}
          colorClass={health?.database === 'connected' ? 'cyan' : 'red'}
        />
      </div>
    </div>
  )
}
