import { motion } from 'framer-motion'
import { formatDistanceToNow } from 'date-fns'
import { LucideIcon } from 'lucide-react'

export interface TimelineEvent {
  id: string
  title: string
  description?: string
  timestamp: string | Date
  icon?: LucideIcon
  color?: 'cyan' | 'magenta' | 'green' | 'orange' | 'red' | 'purple' | 'blue'
  badge?: string
}

interface TimelineProps {
  events: TimelineEvent[]
  maxItems?: number
  onEventClick?: (event: TimelineEvent) => void
}

const colorMap = {
  cyan: { bg: 'bg-neon-cyan', border: 'border-neon-cyan', text: 'text-neon-cyan' },
  magenta: { bg: 'bg-neon-magenta', border: 'border-neon-magenta', text: 'text-neon-magenta' },
  green: { bg: 'bg-neon-green', border: 'border-neon-green', text: 'text-neon-green' },
  orange: { bg: 'bg-neon-orange', border: 'border-neon-orange', text: 'text-neon-orange' },
  red: { bg: 'bg-neon-red', border: 'border-neon-red', text: 'text-neon-red' },
  purple: { bg: 'bg-neon-purple', border: 'border-neon-purple', text: 'text-neon-purple' },
  blue: { bg: 'bg-neon-blue', border: 'border-neon-blue', text: 'text-neon-blue' },
}

export default function Timeline({ events, maxItems, onEventClick }: TimelineProps) {
  const displayEvents = maxItems ? events.slice(0, maxItems) : events

  return (
    <div className="relative">
      {/* Vertical line */}
      <div className="absolute left-[11px] top-0 bottom-0 w-px bg-gradient-to-b from-glass-border via-glass-border to-transparent" />

      <div className="space-y-4">
        {displayEvents.map((event, index) => {
          const colors = colorMap[event.color || 'cyan']
          const Icon = event.icon

          return (
            <motion.div
              key={event.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05, duration: 0.3 }}
              className={`relative flex gap-4 pl-8 ${onEventClick ? 'cursor-pointer hover:opacity-80' : ''}`}
              onClick={() => onEventClick?.(event)}
            >
              {/* Dot */}
              <div className={`absolute left-0 top-1 w-6 h-6 rounded-full ${colors.bg}/20 border-2 ${colors.border} flex items-center justify-center`}>
                {Icon ? (
                  <Icon className={`w-3 h-3 ${colors.text}`} />
                ) : (
                  <div className={`w-2 h-2 rounded-full ${colors.bg}`} />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 pb-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-text-primary truncate">
                      {event.title}
                    </p>
                    {event.description && (
                      <p className="text-xs text-text-secondary mt-0.5 line-clamp-2">
                        {event.description}
                      </p>
                    )}
                  </div>
                  <div className="flex-shrink-0 flex flex-col items-end gap-1">
                    <span className="text-xs text-text-muted whitespace-nowrap">
                      {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                    </span>
                    {event.badge && (
                      <span className={`badge badge-${event.color || 'cyan'}`}>
                        {event.badge}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
