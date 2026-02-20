const API_BASE = '/api'

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'error'
  latency_ms: number
  database: string
  artifact_count?: number
  error?: string
  timestamp: string
}

export interface StatsResponse {
  total: number
  by_type: Record<string, number>
  by_sensitivity: Record<string, number>
  recent_24h: number
  last_activity: string | null
  timestamp: string
}

export interface Artifact {
  id: string
  type: string
  created_at: string
  updated_at: string | null
  sensitivity: string
  title: string | null
  tags: string[]
  source_workflow: string | null
}

export interface ArtifactsResponse {
  artifacts: Artifact[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

async function fetchJSON<T>(url: string): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

export interface Decision extends Artifact {
  decision?: string
  rationale?: string
  outcome_status?: 'pending' | 'validated' | 'reversed' | 'superseded'
}

export interface DecisionsResponse {
  decisions: Decision[]
  total: number
  has_more: boolean
}

export interface ActionItem {
  type: 'unreviewed_decision'
  id: string
  title: string
  age_days: number
  priority: 'high' | 'medium' | 'low'
}

export interface InsightsSummary {
  total_facts: number
  total_decisions: number
  pending_review: number
  oldest_unreviewed_days: number
  recent_24h: number
}

export interface InsightsResponse {
  summary: InsightsSummary
  action_items: ActionItem[]
  timestamp: string
}

export const api = {
  health: () => fetchJSON<HealthResponse>('/health'),
  stats: () => fetchJSON<StatsResponse>('/stats'),
  artifacts: (params?: { type?: string; limit?: number; offset?: number; search?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.type) searchParams.set('type', params.type)
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())
    if (params?.search) searchParams.set('search', params.search)
    const query = searchParams.toString()
    return fetchJSON<ArtifactsResponse>(`/artifacts${query ? `?${query}` : ''}`)
  },
  artifact: (id: string) => fetchJSON<Artifact & { content?: unknown }>(`/artifacts/${id}`),
  decisions: (params?: { status?: string; limit?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.status) searchParams.set('status', params.status)
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    const query = searchParams.toString()
    return fetchJSON<DecisionsResponse>(`/decisions${query ? `?${query}` : ''}`)
  },
  insights: () => fetchJSON<InsightsResponse>('/insights'),
}
