import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useInsights() {
  return useQuery({
    queryKey: ['insights'],
    queryFn: () => api.insights(),
    refetchInterval: 30000, // Refresh every 30s per spec
  })
}
