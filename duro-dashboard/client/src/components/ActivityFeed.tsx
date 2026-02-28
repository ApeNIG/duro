import { useActivity, ActivityEvent } from '@/hooks/useActivity'

const typeColors: Record<string, string> = {
  fact: 'text-[#00FFE5]',      // cyan - tag-fact
  decision: 'text-[#B14EFF]',  // purple - tag-decision
  episode: 'text-[#FF6B00]',   // orange - tag-episode
  evaluation: 'text-[#FF6B00]',
  skill: 'text-[#39FF14]',     // green - tag-skill
  audit: 'text-[#FF2D55]',     // red - tag-audit
  rule: 'text-[#FF2D55]',
  log: 'text-text-muted',
}

function formatTime(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function LogEntry({ event }: { event: ActivityEvent }) {
  const colorClass = typeColors[event.type] || 'text-text-secondary'

  return (
    <div className="log-entry">
      <span className="log-time">{formatTime(event.created_at)}</span>
      <span className={`log-type ${colorClass}`}>[{event.type}]</span>
      <span className="log-message truncate">
        {event.title || event.id.slice(0, 12)}
      </span>
    </div>
  )
}

export default function ActivityFeed() {
  const { events, connected } = useActivity()

  return (
    <div className="flex flex-col gap-4 h-full min-h-0 overflow-hidden">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div className="font-mono text-xs text-text-muted"># recent activity</div>
        <div className="flex items-center gap-2 font-mono text-[10px]">
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-accent animate-pulse' : 'bg-error'}`} />
          <span className={connected ? 'text-accent' : 'text-error'}>
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>

      {/* Log Entries */}
      <div className="flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <div className="font-mono text-xs text-text-muted">
            <span className="text-text-dim">// </span>
            Waiting for activity...
          </div>
        ) : (
          <div className="space-y-0">
            {events.map((event) => (
              <LogEntry key={`${event.id}-${event.created_at}`} event={event} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
