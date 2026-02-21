import { Database, FileText, Brain, Clock, ScrollText, AlertTriangle, Zap, GitCommit } from 'lucide-react'
import { useStats } from '@/hooks/useStats'

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string | number
  subtext?: string
  color?: string
}

function StatCard({ icon, label, value, subtext, color = 'text-accent' }: StatCardProps) {
  return (
    <div className="bg-card border border-border rounded-lg p-3 hover:border-accent/30 transition-colors">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded bg-accent-dim ${color}`}>{icon}</div>
        <div>
          <div className="text-xl font-display font-semibold tracking-tight">{value}</div>
          <div className="text-xs text-text-secondary">{label}</div>
        </div>
      </div>
      {subtext && <div className="text-xs text-text-secondary/60 mt-2 pl-11">{subtext}</div>}
    </div>
  )
}

export default function StatsGrid() {
  const { data, isLoading } = useStats()

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3">
        {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
          <div
            key={i}
            className="bg-card border border-border rounded-lg p-3 h-20 animate-pulse"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-border rounded" />
              <div className="space-y-1.5">
                <div className="w-12 h-5 bg-border rounded" />
                <div className="w-16 h-3 bg-border rounded" />
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  const facts = data?.by_type?.fact || 0
  const decisions = data?.by_type?.decision || 0
  const episodes = data?.by_type?.episode || 0
  const logs = data?.by_type?.log || 0
  const evaluations = data?.by_type?.evaluation || 0
  const incidents = data?.by_type?.incident_rca || data?.by_type?.incident || 0
  const skills = data?.by_type?.skill || data?.by_type?.skill_stats || 0
  const recentChanges = data?.by_type?.recent_change || 0

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3">
      <StatCard
        icon={<Database className="w-4 h-4" />}
        label="Total Artifacts"
        value={data?.total?.toLocaleString() || '0'}
        subtext={`${data?.recent_24h || 0} in last 24h`}
      />
      <StatCard
        icon={<FileText className="w-4 h-4" />}
        label="Facts"
        value={facts.toLocaleString()}
        color="text-green-400"
      />
      <StatCard
        icon={<Brain className="w-4 h-4" />}
        label="Decisions"
        value={decisions.toLocaleString()}
        subtext={`${evaluations} evaluations`}
        color="text-purple-400"
      />
      <StatCard
        icon={<Clock className="w-4 h-4" />}
        label="Episodes"
        value={episodes.toLocaleString()}
        color="text-orange-400"
      />
      <StatCard
        icon={<ScrollText className="w-4 h-4" />}
        label="Logs"
        value={logs.toLocaleString()}
        subtext={`${((logs / (data?.total || 1)) * 100).toFixed(0)}% of total`}
        color="text-gray-400"
      />
      <StatCard
        icon={<AlertTriangle className="w-4 h-4" />}
        label="Incidents"
        value={incidents.toLocaleString()}
        color="text-red-400"
      />
      <StatCard
        icon={<Zap className="w-4 h-4" />}
        label="Skills"
        value={skills.toLocaleString()}
        color="text-cyan-400"
      />
      <StatCard
        icon={<GitCommit className="w-4 h-4" />}
        label="Recent Changes"
        value={recentChanges.toLocaleString()}
        color="text-yellow-400"
      />
    </div>
  )
}
