import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Shield, AlertTriangle, CheckCircle, XCircle, Lock, Eye, Clock } from 'lucide-react'
import GlassPanel from '@/components/layout/GlassPanel'
import SectionHeader from '@/components/layout/SectionHeader'
import MetricCard from '@/components/viz/MetricCard'
import RadialGauge from '@/components/viz/RadialGauge'
import Timeline, { TimelineEvent } from '@/components/viz/Timeline'
import { formatDistanceToNow } from 'date-fns'

interface AuditEntry {
  event_type: string
  severity: string
  decision?: string
  tool?: string
  timestamp: string
  message?: string
  action_id?: string
}

interface GateEntry {
  decision: string
  tool: string
  timestamp: string
  reason?: string
  action_id?: string
}

interface DomainScore {
  domain: string
  score: number
  total_actions: number
  success_rate: number
  last_action?: string
}

interface ActiveApproval {
  action_id: string
  expires_at: string
  reason?: string
}

const severityColors: Record<string, 'cyan' | 'green' | 'orange' | 'red'> = {
  info: 'cyan',
  warn: 'orange',
  high: 'red',
  critical: 'red',
}

const decisionColors: Record<string, 'green' | 'orange' | 'red'> = {
  ALLOW: 'green',
  DENY: 'red',
  NEED_APPROVAL: 'orange',
}

export default function Security() {
  const { data: summary } = useQuery({
    queryKey: ['security-summary'],
    queryFn: () => fetch('/api/security/summary').then(r => r.json()),
    refetchInterval: 10000,
  })

  const { data: auditData } = useQuery({
    queryKey: ['security-audit'],
    queryFn: () => fetch('/api/security/audit?limit=20').then(r => r.json()),
    refetchInterval: 10000,
  })

  const { data: gateData } = useQuery({
    queryKey: ['security-gate'],
    queryFn: () => fetch('/api/security/gate?limit=20').then(r => r.json()),
    refetchInterval: 10000,
  })

  const { data: autonomyData } = useQuery({
    queryKey: ['security-autonomy'],
    queryFn: () => fetch('/api/security/autonomy').then(r => r.json()),
    refetchInterval: 10000,
  })

  // Convert audit entries to timeline events
  const auditEvents: TimelineEvent[] = (auditData?.entries || []).map((entry: AuditEntry) => ({
    id: `${entry.timestamp}-${entry.event_type}`,
    title: entry.event_type.replace(/_/g, ' ').replace(/\./g, ' > '),
    description: entry.message || entry.action_id,
    timestamp: entry.timestamp,
    color: severityColors[entry.severity] || 'cyan',
    badge: entry.severity,
  }))

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-neon-purple/10 border border-neon-purple/30">
            <Shield className="w-6 h-6 text-neon-purple" />
          </div>
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Security Center</h1>
            <p className="text-sm text-text-secondary">Audit logs, policy gate, and autonomy system</p>
          </div>
        </div>
      </motion.div>

      {/* Summary Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Audit Events"
          value={summary?.audit?.total_events || 0}
          icon={Eye}
          color="cyan"
        />
        <MetricCard
          label="Gate Decisions"
          value={summary?.gate?.total_decisions || 0}
          icon={Lock}
          color="purple"
        />
        <MetricCard
          label="Deny Rate"
          value={summary?.gate?.deny_rate || 0}
          format="percent"
          icon={XCircle}
          color="red"
        />
        <MetricCard
          label="Autonomy Score"
          value={(summary?.autonomy?.overall_score || 0.5) * 100}
          format="percent"
          icon={CheckCircle}
          color="green"
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Audit Log */}
        <GlassPanel variant="card" padding="lg" className="lg:col-span-2">
          <SectionHeader title="Audit Log" icon={Eye} />
          {auditEvents.length > 0 ? (
            <Timeline events={auditEvents} maxItems={10} />
          ) : (
            <div className="text-center py-8 text-text-muted">
              No audit events recorded
            </div>
          )}
        </GlassPanel>

        {/* Autonomy System */}
        <GlassPanel variant="card" padding="lg">
          <SectionHeader title="Autonomy System" icon={Shield} />

          <div className="flex justify-center mb-6">
            <RadialGauge
              value={(autonomyData?.overall_score || 0.5) * 100}
              label="Overall Reputation"
              color="purple"
              size="lg"
            />
          </div>

          <div className="space-y-3">
            <h4 className="text-xs uppercase tracking-wider text-text-muted">Domain Scores</h4>
            {(autonomyData?.domains || []).slice(0, 5).map((domain: DomainScore) => (
              <div key={domain.domain} className="flex items-center justify-between">
                <span className="text-sm text-text-secondary truncate max-w-[120px]">
                  {domain.domain.replace(/_/g, ' ')}
                </span>
                <div className="flex items-center gap-3">
                  <div className="w-24 h-2 bg-bg-card rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${domain.score * 100}%` }}
                      transition={{ duration: 0.5 }}
                      className={`h-full ${domain.score > 0.7 ? 'bg-neon-green' : domain.score > 0.4 ? 'bg-neon-orange' : 'bg-neon-red'}`}
                    />
                  </div>
                  <span className="text-xs font-mono text-text-primary w-12 text-right">
                    {Math.round(domain.score * 100)}%
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Active Approvals */}
          {(autonomyData?.active_approvals || []).length > 0 && (
            <div className="mt-6 pt-4 border-t border-glass-border">
              <h4 className="text-xs uppercase tracking-wider text-text-muted mb-3">Active Approvals</h4>
              <div className="space-y-2">
                {autonomyData.active_approvals.map((approval: ActiveApproval) => (
                  <div
                    key={approval.action_id}
                    className="flex items-center justify-between p-2 rounded-lg bg-bg-card/50"
                  >
                    <span className="text-xs text-text-secondary truncate max-w-[140px]">
                      {approval.action_id.split(':')[0]}
                    </span>
                    <span className="text-xs text-neon-orange flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDistanceToNow(new Date(approval.expires_at))}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </GlassPanel>
      </div>

      {/* Policy Gate Stats */}
      <GlassPanel variant="card" padding="lg">
        <SectionHeader title="Policy Gate Decisions" icon={Lock} />

        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="text-center p-4 rounded-lg bg-neon-green/10 border border-neon-green/30">
            <div className="text-2xl font-bold text-neon-green font-mono">
              {gateData?.stats?.ALLOW || 0}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wider mt-1">Allowed</div>
          </div>
          <div className="text-center p-4 rounded-lg bg-neon-orange/10 border border-neon-orange/30">
            <div className="text-2xl font-bold text-neon-orange font-mono">
              {gateData?.stats?.NEED_APPROVAL || 0}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wider mt-1">Needs Approval</div>
          </div>
          <div className="text-center p-4 rounded-lg bg-neon-red/10 border border-neon-red/30">
            <div className="text-2xl font-bold text-neon-red font-mono">
              {gateData?.stats?.DENY || 0}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wider mt-1">Denied</div>
          </div>
        </div>

        {/* Recent Gate Decisions */}
        <div className="space-y-2">
          {(gateData?.entries || []).slice(0, 5).map((entry: GateEntry, idx: number) => (
            <motion.div
              key={`${entry.timestamp}-${idx}`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05 }}
              className="flex items-center justify-between p-3 rounded-lg bg-bg-card/50 border border-glass-border"
            >
              <div className="flex items-center gap-3">
                {entry.decision === 'ALLOW' && <CheckCircle className="w-4 h-4 text-neon-green" />}
                {entry.decision === 'DENY' && <XCircle className="w-4 h-4 text-neon-red" />}
                {entry.decision === 'NEED_APPROVAL' && <AlertTriangle className="w-4 h-4 text-neon-orange" />}
                <span className="text-sm text-text-primary">{entry.tool}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className={`badge badge-${decisionColors[entry.decision] || 'cyan'}`}>
                  {entry.decision}
                </span>
                <span className="text-xs text-text-muted">
                  {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      </GlassPanel>
    </div>
  )
}
