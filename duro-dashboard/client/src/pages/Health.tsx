import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Heart, RefreshCw, Pin, Trash2, AlertCircle, Database, Activity, CheckCircle } from 'lucide-react'
import GlassPanel from '@/components/layout/GlassPanel'
import SectionHeader from '@/components/layout/SectionHeader'
import MetricCard from '@/components/viz/MetricCard'
import RadialGauge from '@/components/viz/RadialGauge'
import { formatDistanceToNow } from 'date-fns'

interface DecayFact {
  id: string
  claim: string
  confidence: number
  importance: number
  reinforcement_count: number
  verification_state: string
  days_since_update: number
  updated_at: string
}

interface MaintenanceReport {
  facts: {
    total: number
    pinned: number
    pinned_pct: number
    stale: number
    stale_pct: number
    unverified: number
    low_confidence: number
  }
  artifact_counts: Record<string, number>
  health_score: number
}

interface EmbeddingStatus {
  total_artifacts: number
  embedded: number
  coverage_pct: number
  missing: number
}

const verificationColors: Record<string, 'cyan' | 'green' | 'orange' | 'red'> = {
  verified: 'green',
  unverified: 'orange',
  disputed: 'red',
  stale: 'orange',
}

export default function Health() {
  const { data: maintenance } = useQuery<MaintenanceReport>({
    queryKey: ['health-maintenance'],
    queryFn: () => fetch('/api/health/maintenance').then(r => r.json()),
    refetchInterval: 30000,
  })

  const { data: decayQueue } = useQuery<{ queue: DecayFact[] }>({
    queryKey: ['health-decay-queue'],
    queryFn: () => fetch('/api/health/decay-queue?limit=10').then(r => r.json()),
    refetchInterval: 30000,
  })

  const { data: embeddings } = useQuery<EmbeddingStatus>({
    queryKey: ['health-embeddings'],
    queryFn: () => fetch('/api/health/embedding-status').then(r => r.json()),
    refetchInterval: 30000,
  })

  const handleReinforce = async (factId: string) => {
    // TODO: Call reinforce API
    console.log('Reinforce fact:', factId)
  }

  const handlePin = async (factId: string) => {
    // TODO: Call pin API
    console.log('Pin fact:', factId)
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-neon-green/10 border border-neon-green/30">
            <Heart className="w-6 h-6 text-neon-green" />
          </div>
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Health & Maintenance</h1>
            <p className="text-sm text-text-secondary">Decay queue, memory health, and maintenance actions</p>
          </div>
        </div>
      </motion.div>

      {/* Health Score & Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Health Score"
          value={maintenance?.health_score || 0}
          format="percent"
          icon={Heart}
          color="green"
          glow
        />
        <MetricCard
          label="Total Facts"
          value={maintenance?.facts.total || 0}
          icon={Database}
          color="cyan"
        />
        <MetricCard
          label="Stale Facts"
          value={maintenance?.facts.stale || 0}
          icon={AlertCircle}
          color="orange"
        />
        <MetricCard
          label="Embedding Coverage"
          value={embeddings?.coverage_pct || 0}
          format="percent"
          icon={Activity}
          color="purple"
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Decay Queue */}
        <GlassPanel variant="card" padding="lg" className="lg:col-span-2">
          <SectionHeader
            title="Decay Queue"
            icon={RefreshCw}
            badge={decayQueue?.queue.length}
            badgeColor="orange"
          />
          <p className="text-xs text-text-muted mb-4">
            Facts sorted by staleness score (age x importance / reinforcements). Review to Pin, Reinforce, or Delete.
          </p>

          <div className="space-y-3">
            {(decayQueue?.queue || []).map((fact, idx) => (
              <motion.div
                key={fact.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="p-4 rounded-lg bg-bg-card/50 border border-glass-border hover:border-neon-cyan/30 transition-all"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text-primary line-clamp-2">{fact.claim}</p>
                    <div className="flex items-center gap-3 mt-2">
                      <span className={`badge badge-${verificationColors[fact.verification_state] || 'cyan'}`}>
                        {fact.verification_state}
                      </span>
                      <span className="text-xs text-text-muted">
                        Conf: {Math.round(fact.confidence * 100)}%
                      </span>
                      <span className="text-xs text-text-muted">
                        Imp: {Math.round(fact.importance * 100)}%
                      </span>
                      <span className="text-xs text-text-muted">
                        Reinforced: {fact.reinforcement_count}x
                      </span>
                    </div>
                    <p className="text-xs text-text-muted mt-1">
                      Last updated {formatDistanceToNow(new Date(fact.updated_at), { addSuffix: true })}
                      {' '}({fact.days_since_update} days ago)
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => handleReinforce(fact.id)}
                      className="p-2 rounded-lg bg-neon-green/10 hover:bg-neon-green/20 text-neon-green transition-colors"
                      title="Reinforce"
                    >
                      <CheckCircle className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handlePin(fact.id)}
                      className="p-2 rounded-lg bg-neon-cyan/10 hover:bg-neon-cyan/20 text-neon-cyan transition-colors"
                      title="Pin"
                    >
                      <Pin className="w-4 h-4" />
                    </button>
                    <button
                      className="p-2 rounded-lg bg-neon-red/10 hover:bg-neon-red/20 text-neon-red transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}

            {(!decayQueue?.queue || decayQueue.queue.length === 0) && (
              <div className="text-center py-8 text-text-muted">
                No facts in decay queue
              </div>
            )}
          </div>
        </GlassPanel>

        {/* Health Gauges */}
        <GlassPanel variant="card" padding="lg">
          <SectionHeader title="Memory Health" icon={Heart} />

          <div className="grid grid-cols-2 gap-4 mb-6">
            <RadialGauge
              value={100 - (maintenance?.facts.stale_pct || 0)}
              label="Freshness"
              color="green"
              size="md"
            />
            <RadialGauge
              value={maintenance?.facts.pinned_pct || 0}
              label="Pinned"
              color="cyan"
              size="md"
            />
            <RadialGauge
              value={embeddings?.coverage_pct || 0}
              label="Embedded"
              color="purple"
              size="md"
            />
            <RadialGauge
              value={maintenance?.health_score || 0}
              label="Overall"
              color="green"
              size="md"
              thresholds={{ warning: 70, critical: 40 }}
            />
          </div>

          {/* Artifact Distribution */}
          <div className="pt-4 border-t border-glass-border">
            <h4 className="text-xs uppercase tracking-wider text-text-muted mb-3">Artifact Distribution</h4>
            <div className="space-y-2">
              {Object.entries(maintenance?.artifact_counts || {})
                .sort(([, a], [, b]) => b - a)
                .slice(0, 6)
                .map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary capitalize">{type.replace(/_/g, ' ')}</span>
                    <span className="font-mono text-text-primary">{count}</span>
                  </div>
                ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="mt-6 pt-4 border-t border-glass-border">
            <h4 className="text-xs uppercase tracking-wider text-text-muted mb-3">Maintenance Actions</h4>
            <div className="space-y-2">
              <button className="w-full px-4 py-2 rounded-lg bg-bg-card/50 hover:bg-bg-card border border-glass-border hover:border-neon-cyan/30 text-sm text-text-secondary hover:text-text-primary transition-all flex items-center gap-2">
                <RefreshCw className="w-4 h-4" />
                Apply Decay
              </button>
              <button className="w-full px-4 py-2 rounded-lg bg-bg-card/50 hover:bg-bg-card border border-glass-border hover:border-neon-cyan/30 text-sm text-text-secondary hover:text-text-primary transition-all flex items-center gap-2">
                <Database className="w-4 h-4" />
                Prune Orphans
              </button>
              <button className="w-full px-4 py-2 rounded-lg bg-bg-card/50 hover:bg-bg-card border border-glass-border hover:border-neon-cyan/30 text-sm text-text-secondary hover:text-text-primary transition-all flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Reindex
              </button>
            </div>
          </div>
        </GlassPanel>
      </div>
    </div>
  )
}
