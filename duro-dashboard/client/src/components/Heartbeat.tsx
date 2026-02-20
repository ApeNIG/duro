import { useHeartbeat } from '@/hooks/useHeartbeat'

export default function Heartbeat() {
  const { data, connected } = useHeartbeat()

  const isHealthy = connected && data?.status === 'healthy'

  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <div
          className={`w-2.5 h-2.5 rounded-full ${
            isHealthy ? 'bg-accent' : connected ? 'bg-warning' : 'bg-error'
          }`}
        />
        {isHealthy && (
          <div className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-accent animate-ping opacity-75" />
        )}
      </div>
      <span className="text-xs text-text-secondary font-mono">
        {connected ? (
          data?.latency_ms !== undefined ? (
            <span className={data.latency_ms < 50 ? 'text-accent' : 'text-text-secondary'}>
              {data.latency_ms.toFixed(0)}ms
            </span>
          ) : (
            'connecting...'
          )
        ) : (
          <span className="text-error">offline</span>
        )}
      </span>
    </div>
  )
}
