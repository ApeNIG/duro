import { useState, useEffect, useRef, useCallback } from 'react'

export interface ActivityEvent {
  id: string
  type: string
  created_at: string
  updated_at: string | null
  title: string | null
  sensitivity: string
  tags: string[]
  source_workflow: string | null
}

export function useActivity(maxItems = 50) {
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [connected, setConnected] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const eventSource = new EventSource('/api/stream/activity')
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }

    eventSource.addEventListener('connected', () => {
      setConnected(true)
    })

    eventSource.addEventListener('artifact', (event) => {
      try {
        const artifact: ActivityEvent = JSON.parse(event.data)
        setEvents((prev) => {
          const updated = [artifact, ...prev]
          return updated.slice(0, maxItems)
        })
      } catch {
        console.error('Failed to parse activity event')
      }
    })

    eventSource.onerror = () => {
      setConnected(false)
      eventSource.close()

      // Reconnect after 5 seconds
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect()
      }, 5000)
    }
  }, [maxItems])

  useEffect(() => {
    connect()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [connect])

  const status = connected ? 'connected' : 'disconnected'
  return { events, connected, status }
}
