import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Link2, Lightbulb, AlertCircle, TrendingUp, Sparkles, GitMerge, Zap } from 'lucide-react'
import GlassPanel from '@/components/layout/GlassPanel'
import SectionHeader from '@/components/layout/SectionHeader'
import MetricCard from '@/components/viz/MetricCard'

interface OrphanArtifact {
  id: string
  title: string
  type: string
  connection_count: number
  created_at: string
}

interface DriftItem {
  stated: string
  observed: string
  severity: 'low' | 'medium' | 'high'
}

interface Idea {
  id: string
  title: string
  description: string
  source: string
  potential: number
}

interface CrossConnection {
  from_domain: string
  to_domain: string
  concept: string
  strength: number
}

export default function Emergence() {
  // Connect to real API endpoints
  const { data: orphans, isLoading: orphansLoading } = useQuery({
    queryKey: ['emergence-orphans'],
    queryFn: async () => {
      const res = await fetch('/api/emergence/orphans')
      if (!res.ok) throw new Error('Failed to fetch orphans')
      return res.json()
    },
    refetchInterval: 60000,
  })

  const { data: driftReport, isLoading: driftLoading } = useQuery({
    queryKey: ['emergence-drift'],
    queryFn: async () => {
      const res = await fetch('/api/emergence/drift')
      if (!res.ok) throw new Error('Failed to fetch drift report')
      return res.json()
    },
    refetchInterval: 60000,
  })

  const { data: ideas, isLoading: ideasLoading } = useQuery({
    queryKey: ['emergence-ideas'],
    queryFn: async () => {
      const res = await fetch('/api/emergence/ideas')
      if (!res.ok) throw new Error('Failed to fetch ideas')
      return res.json()
    },
    refetchInterval: 60000,
  })

  const { data: connections, isLoading: connectionsLoading } = useQuery({
    queryKey: ['emergence-connections'],
    queryFn: async () => {
      const res = await fetch('/api/emergence/connections')
      if (!res.ok) throw new Error('Failed to fetch connections')
      return res.json()
    },
    refetchInterval: 60000,
  })

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-neon-magenta/10 border border-neon-magenta/30">
            <Link2 className="w-6 h-6 text-neon-magenta" />
          </div>
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Emergence</h1>
            <p className="text-sm text-text-secondary">Orphan detection, drift reports, ideas, and cross-domain connections</p>
          </div>
        </div>
      </motion.div>

      {/* Summary Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Orphan Artifacts"
          value={orphans?.artifacts.length || 0}
          icon={AlertCircle}
          color="orange"
        />
        <MetricCard
          label="Drift Items"
          value={driftReport?.items.length || 0}
          icon={TrendingUp}
          color="red"
        />
        <MetricCard
          label="Generated Ideas"
          value={ideas?.items.length || 0}
          icon={Lightbulb}
          color="magenta"
        />
        <MetricCard
          label="Cross-Connections"
          value={connections?.items.length || 0}
          icon={GitMerge}
          color="cyan"
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Orphan Artifacts */}
        <GlassPanel variant="card" padding="lg">
          <SectionHeader
            title="Orphan Artifacts"
            icon={AlertCircle}
            badge={orphans?.artifacts.length}
            badgeColor="orange"
          />
          <p className="text-xs text-text-muted mb-4">
            Under-connected artifacts that may need linking or removal
          </p>

          <div className="space-y-3">
            {(orphans?.artifacts || []).map((artifact, idx) => (
              <motion.div
                key={artifact.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="p-3 rounded-lg bg-bg-card/50 border border-glass-border hover:border-neon-orange/30 transition-all"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm text-text-primary">{artifact.title}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="badge badge-orange">{artifact.type}</span>
                      <span className="text-xs text-text-muted">
                        {artifact.connection_count} connections
                      </span>
                    </div>
                  </div>
                  <button className="p-2 rounded-lg bg-neon-cyan/10 hover:bg-neon-cyan/20 text-neon-cyan transition-colors">
                    <Link2 className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            ))}

            {(!orphans?.artifacts || orphans.artifacts.length === 0) && (
              <div className="text-center py-6 text-text-muted">
                No orphan artifacts detected
              </div>
            )}
          </div>
        </GlassPanel>

        {/* Drift Report */}
        <GlassPanel variant="card" padding="lg">
          <SectionHeader
            title="Drift Report"
            icon={TrendingUp}
            badge={driftReport?.items.length}
            badgeColor="red"
          />
          <p className="text-xs text-text-muted mb-4">
            Discrepancies between stated rules and observed behavior
          </p>

          <div className="space-y-3">
            {(driftReport?.items || []).map((item, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className={`p-3 rounded-lg border transition-all ${
                  item.severity === 'high'
                    ? 'bg-neon-red/10 border-neon-red/30'
                    : item.severity === 'medium'
                    ? 'bg-neon-orange/10 border-neon-orange/30'
                    : 'bg-bg-card/50 border-glass-border'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`badge ${
                    item.severity === 'high' ? 'badge-red' :
                    item.severity === 'medium' ? 'badge-orange' : 'badge-cyan'
                  }`}>
                    {item.severity}
                  </span>
                </div>
                <p className="text-xs text-text-secondary">
                  <strong>Stated:</strong> {item.stated}
                </p>
                <p className="text-xs text-text-secondary mt-1">
                  <strong>Observed:</strong> {item.observed}
                </p>
              </motion.div>
            ))}

            {(!driftReport?.items || driftReport.items.length === 0) && (
              <div className="text-center py-6 text-text-muted">
                No drift detected
              </div>
            )}
          </div>
        </GlassPanel>

        {/* Generated Ideas */}
        <GlassPanel variant="card" padding="lg">
          <SectionHeader
            title="Idea Generation"
            icon={Lightbulb}
            badge={ideas?.items.length}
            badgeColor="magenta"
          />
          <p className="text-xs text-text-muted mb-4">
            AI-generated ideas from pattern analysis
          </p>

          <div className="space-y-3">
            {(ideas?.items || []).map((idea, idx) => (
              <motion.div
                key={idea.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="p-3 rounded-lg bg-bg-card/50 border border-glass-border hover:border-neon-magenta/30 transition-all"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Sparkles className="w-4 h-4 text-neon-magenta" />
                      <p className="text-sm font-medium text-text-primary">{idea.title}</p>
                    </div>
                    <p className="text-xs text-text-secondary">{idea.description}</p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="badge badge-purple">{idea.source}</span>
                      <span className="text-xs text-text-muted">
                        Potential: {Math.round(idea.potential * 100)}%
                      </span>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}

            {(!ideas?.items || ideas.items.length === 0) && (
              <div className="text-center py-6 text-text-muted">
                No ideas generated yet
              </div>
            )}
          </div>
        </GlassPanel>

        {/* Cross-Domain Connections */}
        <GlassPanel variant="card" padding="lg">
          <SectionHeader
            title="Cross-Domain Connections"
            icon={GitMerge}
            badge={connections?.items.length}
            badgeColor="cyan"
          />
          <p className="text-xs text-text-muted mb-4">
            Discovered patterns across different project domains
          </p>

          <div className="space-y-3">
            {(connections?.items || []).map((conn, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="p-3 rounded-lg bg-bg-card/50 border border-glass-border hover:border-neon-cyan/30 transition-all"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="badge badge-blue">{conn.from_domain}</span>
                  <Zap className="w-3 h-3 text-neon-cyan" />
                  <span className="badge badge-purple">{conn.to_domain}</span>
                </div>
                <p className="text-xs text-text-secondary">
                  <strong>Concept:</strong> {conn.concept}
                </p>
                <div className="mt-2">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-text-muted">Connection Strength</span>
                    <span className="text-neon-cyan">{Math.round(conn.strength * 100)}%</span>
                  </div>
                  <div className="h-1 bg-bg-card rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${conn.strength * 100}%` }}
                      transition={{ duration: 0.5 }}
                      className="h-full bg-neon-cyan"
                    />
                  </div>
                </div>
              </motion.div>
            ))}

            {(!connections?.items || connections.items.length === 0) && (
              <div className="text-center py-6 text-text-muted">
                No cross-domain connections found
              </div>
            )}
          </div>
        </GlassPanel>
      </div>
    </div>
  )
}
