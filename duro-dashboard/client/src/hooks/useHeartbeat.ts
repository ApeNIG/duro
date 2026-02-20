import { useState, useEffect, useRef, useCallback } from 'react'

export interface HeartbeatData {
  status: 'healthy' | 'error'
  latency_ms: number
  artifact_count?: number
  timestamp: string
  error?: string
}

export function useHeartbeat() {
  const [data, setData] = useState<HeartbeatData | null>(null)
  const [connected, setConnected] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const eventSource = new EventSource('/api/stream/heartbeat')
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      setConnected(true)
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }

    eventSource.addEventListener('heartbeat', (event) => {
      try {
        const parsed = JSON.parse(event.data)
        setData(parsed)
      } catch {
        console.error('Failed to parse heartbeat data')
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
  }, [])

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

  return { data, connected }
}
