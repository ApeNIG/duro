import { useActivity, ActivityEvent } from '@/hooks/useActivity'
import { Circle, Zap } from 'lucide-react'

const typeColors: Record<string, string> = {
  fact: 'text-blue-400',
  decision: 'text-purple-400',
  episode: 'text-orange-400',
  evaluation: 'text-yellow-400',
  skill: 'text-green-400',
  rule: 'text-red-400',
  log: 'text-gray-400',
}

function formatTime(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function ActivityItem({ event }: { event: ActivityEvent }) {
  const colorClass = typeColors[event.type] || 'text-text-secondary'

  return (
    <div className="flex items-start gap-3 py-2 px-3 hover:bg-white/5 rounded transition-colors animate-fade-in">
      <Circle className={`w-2 h-2 mt-1.5 fill-current ${colorClass}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-mono uppercase ${colorClass}`}>{event.type}</span>
          <span className="text-xs text-text-secondary/50">{formatTime(event.created_at)}</span>
        </div>
        <div className="text-sm text-text-primary truncate mt-0.5">
          {event.title || event.id.slice(0, 12)}
        </div>
      </div>
    </div>
  )
}

export default function ActivityFeed() {
  const { events, connected } = useActivity()

  return (
    <div className="bg-card border border-border rounded-lg h-full flex flex-col min-h-0 overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-accent" />
          <span className="text-sm font-medium">Live Activity</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div
            className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-accent' : 'bg-error'}`}
          />
          <span className="text-xs text-text-secondary">
            {connected ? 'connected' : 'disconnected'}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <div className="p-4 text-center text-text-secondary text-sm">
            <div className="text-text-secondary/50">Waiting for activity...</div>
            <div className="text-xs mt-1 text-text-secondary/30">
              Create a fact or decision to see it here
            </div>
          </div>
        ) : (
          <div className="p-1">
            {events.map((event) => (
              <ActivityItem key={`${event.id}-${event.created_at}`} event={event} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
