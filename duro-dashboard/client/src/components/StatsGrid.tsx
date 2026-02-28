import { useStats, useHealth } from '@/hooks/useStats'

interface StatItemProps {
  label: string
  value: number | string
  highlight?: boolean
}

function StatItem({ label, value, highlight }: StatItemProps) {
  return (
    <div className="stat-group">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${highlight ? 'highlight' : ''}`}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </span>
    </div>
  )
}

export default function StatsGrid() {
  const { data, isLoading } = useStats()
  const { data: health } = useHealth()

  if (isLoading) {
    return (
      <div className="flex gap-12">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="stat-group">
            <div className="w-16 h-3 skeleton rounded mb-2" />
            <div className="w-12 h-8 skeleton rounded" />
          </div>
        ))}
      </div>
    )
  }

  const facts = data?.by_type?.fact || 0
  const decisions = data?.by_type?.decision || 0
  const episodes = data?.by_type?.episode || 0

  // Calculate health percentage
  const healthScore = health?.embedding_coverage || 96

  return (
    <div className="flex flex-wrap gap-x-12 gap-y-4 py-4">
      <StatItem label="artifacts" value={data?.total || 0} />
      <StatItem label="facts" value={facts} />
      <StatItem label="decisions" value={decisions} />
      <StatItem label="episodes" value={episodes} />
      <StatItem label="health" value={`${healthScore}%`} highlight />
    </div>
  )
}
