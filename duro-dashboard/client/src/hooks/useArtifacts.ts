import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useArtifacts(params?: { type?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['artifacts', params],
    queryFn: () => api.artifacts(params),
    refetchInterval: 15000, // Refresh every 15s
  })
}
