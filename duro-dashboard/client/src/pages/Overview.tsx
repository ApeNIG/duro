import StatsGrid from '@/components/StatsGrid'
import ActivityFeed from '@/components/ActivityFeed'
import MemoryBrowser from '@/components/MemoryBrowser'

export default function Overview() {
  return (
    <div className="h-full flex flex-col gap-6 min-h-0">
      {/* Stats Row */}
      <StatsGrid />

      {/* Main Content */}
      <div className="flex-1 grid grid-cols-2 gap-6 min-h-0">
        <ActivityFeed />
        <MemoryBrowser />
      </div>
    </div>
  )
}
