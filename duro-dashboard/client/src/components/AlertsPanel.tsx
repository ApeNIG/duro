import { Link } from 'react-router-dom'
import { AlertCircle, Clock, FileWarning, ChevronRight, CheckCircle2 } from 'lucide-react'
import { usePendingReviews, useInsights, useDecayQueue } from '@/hooks/useStats'

interface AlertItemProps {
  count: number
  label: string
  linkTo: string
  icon: React.ReactNode
  severity: 'critical' | 'warning' | 'info'
}

function AlertItem({ count, label, linkTo, icon, severity }: AlertItemProps) {
  if (count === 0) return null

  const severityStyles = {
    critical: 'bg-red-500/10 border-red-500/30 hover:bg-red-500/20',
    warning: 'bg-warning/10 border-warning/30 hover:bg-warning/20',
    info: 'bg-accent/10 border-accent/30 hover:bg-accent/20',
  }

  const countStyles = {
    critical: 'text-red-400',
    warning: 'text-warning',
    info: 'text-accent',
  }

  const iconStyles = {
    critical: 'text-red-400',
    warning: 'text-warning',
    info: 'text-accent',
  }

  return (
    <Link
      to={linkTo}
      className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${severityStyles[severity]}`}
    >
      <div className={`flex-shrink-0 ${iconStyles[severity]}`}>
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className={`text-lg font-bold font-mono ${countStyles[severity]}`}>{count}</span>
          <span className="text-xs text-text-secondary truncate">{label}</span>
        </div>
      </div>
      <ChevronRight className="w-4 h-4 text-text-muted flex-shrink-0" />
    </Link>
  )
}

export default function AlertsPanel() {
  const { data: pendingCount = 0 } = usePendingReviews()
  const { data: insights } = useInsights()
  const { data: decayQueue } = useDecayQueue()

  const staleFacts = insights?.summary?.pending_review || 0
  const decayCount = decayQueue?.total || 0

  const hasAlerts = pendingCount > 0 || staleFacts > 0 || decayCount > 0
  const totalAlerts = pendingCount + staleFacts + decayCount

  return (
    <div className="flex flex-col">
      {/* Section Header with count */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-warning" />
          <span className="font-mono text-xs text-text-muted uppercase tracking-wider"># alerts</span>
        </div>
        {hasAlerts && (
          <span className="px-2 py-0.5 text-[10px] font-bold bg-warning/20 text-warning rounded-full">
            {totalAlerts}
          </span>
        )}
      </div>

      {hasAlerts ? (
        <div className="flex flex-col gap-2">
          <AlertItem
            count={pendingCount}
            label="decisions pending review"
            linkTo="/reviews"
            icon={<FileWarning className="w-5 h-5" />}
            severity="warning"
          />
          <AlertItem
            count={staleFacts}
            label="facts need review"
            linkTo="/health"
            icon={<AlertCircle className="w-5 h-5" />}
            severity="warning"
          />
          <AlertItem
            count={decayCount}
            label="in decay queue"
            linkTo="/health"
            icon={<Clock className="w-5 h-5" />}
            severity="info"
          />
        </div>
      ) : (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-green-500/10 border border-green-500/30">
          <CheckCircle2 className="w-5 h-5 text-green-400" />
          <span className="text-sm text-green-400 font-medium">All clear - no alerts</span>
        </div>
      )}
    </div>
  )
}
