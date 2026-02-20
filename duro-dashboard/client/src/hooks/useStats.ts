import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: api.stats,
    refetchInterval: 10000, // Refresh every 10s
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 5000, // Refresh every 5s
  })
}

export function usePendingReviews() {
  return useQuery({
    queryKey: ['decisions', 'pending'],
    queryFn: () => api.decisions({ status: 'pending', limit: 100 }),
    refetchInterval: 30000, // Refresh every 30s
    select: (data) => data.decisions.length,
  })
}
