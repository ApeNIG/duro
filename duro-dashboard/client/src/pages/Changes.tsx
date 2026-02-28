import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Clock, GitCommit, AlertTriangle, Tag, Filter, ChevronRight } from 'lucide-react'
import GlassPanel from '@/components/layout/GlassPanel'
import SectionHeader from '@/components/layout/SectionHeader'
import { formatDistanceToNow, format } from 'date-fns'

interface Change {
  id: string
  scope: string
  change: string
  why?: string
  risk_tags: string[]
  commit_hash?: string
  quick_checks: string[]
  created_at: string
}

interface ChangesResponse {
  changes: Change[]
  total: number
  hours: number
  risk_tag_distribution: Record<string, number>
}

const riskTagColors: Record<string, string> = {
  config: 'badge-cyan',
  db: 'badge-purple',
  paths: 'badge-blue',
  sync: 'badge-orange',
  deploy: 'badge-red',
  auth: 'badge-magenta',
  caching: 'badge-green',
  env: 'badge-orange',
  permissions: 'badge-red',
  network: 'badge-blue',
  state: 'badge-purple',
  api: 'badge-cyan',
  schema: 'badge-magenta',
}

export default function Changes() {
  const [hours, setHours] = useState(48)
  const [selectedTag, setSelectedTag] = useState<string | null>(null)

  const { data: changesData, isLoading } = useQuery<ChangesResponse>({
    queryKey: ['changes', hours],
    queryFn: () => fetch(`/api/changes?hours=${hours}`).then(r => r.json()),
    refetchInterval: 30000,
  })

  const filteredChanges = selectedTag
    ? changesData?.changes.filter(c => c.risk_tags.includes(selectedTag))
    : changesData?.changes

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between flex-wrap gap-4"
      >
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-neon-orange/10 border border-neon-orange/30">
            <Clock className="w-6 h-6 text-neon-orange" />
          </div>
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Change Ledger</h1>
            <p className="text-sm text-text-secondary">48-hour rule - recent structural changes</p>
          </div>
        </div>

        {/* Time Range Selector */}
        <div className="flex items-center gap-2">
          {[24, 48, 72, 168].map((h) => (
            <button
              key={h}
              onClick={() => setHours(h)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                hours === h
                  ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30'
                  : 'bg-bg-card/50 text-text-secondary hover:text-text-primary border border-glass-border'
              }`}
            >
              {h}h
            </button>
          ))}
        </div>
      </motion.div>

      <div className="grid lg:grid-cols-4 gap-6">
        {/* Risk Tag Filter */}
        <GlassPanel variant="card" padding="md">
          <SectionHeader title="Risk Tags" icon={Filter} />
          <div className="space-y-2">
            <button
              onClick={() => setSelectedTag(null)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all ${
                !selectedTag
                  ? 'bg-neon-cyan/20 text-neon-cyan'
                  : 'text-text-secondary hover:text-text-primary hover:bg-white/5'
              }`}
            >
              All Changes ({changesData?.total || 0})
            </button>
            {Object.entries(changesData?.risk_tag_distribution || {})
              .sort(([, a], [, b]) => b - a)
              .map(([tag, count]) => (
                <button
                  key={tag}
                  onClick={() => setSelectedTag(selectedTag === tag ? null : tag)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center justify-between ${
                    selectedTag === tag
                      ? 'bg-neon-cyan/20 text-neon-cyan'
                      : 'text-text-secondary hover:text-text-primary hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Tag className="w-3 h-3" />
                    <span>{tag}</span>
                  </div>
                  <span className="font-mono text-xs">{count}</span>
                </button>
              ))}
          </div>
        </GlassPanel>

        {/* Changes Timeline */}
        <GlassPanel variant="card" padding="lg" className="lg:col-span-3">
          <SectionHeader
            title={`Changes (${hours}h)`}
            icon={GitCommit}
            badge={filteredChanges?.length}
            badgeColor="orange"
          />

          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 rounded-lg skeleton" />
              ))}
            </div>
          ) : filteredChanges && filteredChanges.length > 0 ? (
            <div className="space-y-4">
              {filteredChanges.map((change, idx) => (
                <motion.div
                  key={change.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.03 }}
                  className="p-4 rounded-lg bg-bg-card/50 border border-glass-border hover:border-neon-orange/30 transition-all group"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="badge badge-orange">{change.scope}</span>
                        {change.commit_hash && (
                          <span className="text-xs text-text-muted font-mono">
                            {change.commit_hash.substring(0, 7)}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-text-primary">{change.change}</p>
                      {change.why && (
                        <p className="text-xs text-text-muted mt-1">
                          Why: {change.why}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-1 mt-2">
                        {change.risk_tags.map((tag) => (
                          <span
                            key={tag}
                            className={`badge ${riskTagColors[tag] || 'badge-cyan'}`}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2 flex-shrink-0">
                      <span className="text-xs text-text-muted">
                        {formatDistanceToNow(new Date(change.created_at), { addSuffix: true })}
                      </span>
                      <span className="text-xs text-text-muted">
                        {format(new Date(change.created_at), 'MMM d, HH:mm')}
                      </span>
                    </div>
                  </div>

                  {/* Quick Checks */}
                  {change.quick_checks.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-glass-border">
                      <p className="text-xs text-text-muted mb-2">Quick Checks:</p>
                      <div className="space-y-1">
                        {change.quick_checks.map((check, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs text-text-secondary">
                            <ChevronRight className="w-3 h-3 text-neon-cyan" />
                            <span>{check}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <AlertTriangle className="w-12 h-12 text-text-muted mx-auto mb-4" />
              <p className="text-text-secondary">No changes recorded in the last {hours} hours</p>
              <p className="text-xs text-text-muted mt-1">
                Use `duro_store_change` to log structural changes
              </p>
            </div>
          )}
        </GlassPanel>
      </div>
    </div>
  )
}
