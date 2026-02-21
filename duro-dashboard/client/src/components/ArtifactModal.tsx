import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  X,
  ExternalLink,
  Clock,
  Tag,
  Shield,
  Copy,
  Check,
  History,
  Link2,
  ChevronDown,
  ChevronRight,
  Sparkles,
  AlertCircle,
  Trash2,
  Loader2,
  Network,
  ArrowRight,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { Artifact } from '@/lib/api'
import { useToast } from './Toast'

interface ArtifactModalProps {
  artifactId: string
  onClose: () => void
}

const typeColors: Record<string, string> = {
  fact: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  decision: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  episode: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  evaluation: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  skill: 'bg-green-500/20 text-green-400 border-green-500/30',
  rule: 'bg-red-500/20 text-red-400 border-red-500/30',
  log: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  skill_stats: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  incident_rca: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
  decision_validation: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  recent_change: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  checklist_template: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
  design_reference: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
}

interface ArtifactWithContent extends Artifact {
  content?: Record<string, unknown> | string | null
  file_path?: string
}

interface ValidationEvent {
  id: string
  timestamp: string
  status: string
  result?: string
  expected_outcome?: string
  actual_outcome?: string
  notes?: string
  confidence_delta?: number
}

function formatDateTime(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'today'
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  return `${Math.floor(diffDays / 30)} months ago`
}

// Simple JSON syntax highlighting
function highlightJSON(json: string): JSX.Element[] {
  const lines = json.split('\n')
  return lines.map((line, i) => {
    // Highlight keys
    const highlighted = line
      .replace(/"([^"]+)":/g, '<span class="text-accent">"$1"</span>:')
      .replace(/: "([^"]*)"/g, ': <span class="text-green-400">"$1"</span>')
      .replace(/: (\d+\.?\d*)/g, ': <span class="text-blue-400">$1</span>')
      .replace(/: (true|false)/g, ': <span class="text-purple-400">$1</span>')
      .replace(/: (null)/g, ': <span class="text-gray-500">$1</span>')

    return (
      <div key={i} className="flex">
        <span className="w-8 text-text-secondary/30 select-none text-right pr-2 flex-shrink-0">
          {i + 1}
        </span>
        <span dangerouslySetInnerHTML={{ __html: highlighted }} />
      </div>
    )
  })
}

function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = false,
}: {
  title: string
  icon: React.ElementType
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center gap-2 p-3 bg-card hover:bg-white/5 transition-colors text-left"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-text-secondary" />
        ) : (
          <ChevronRight className="w-4 h-4 text-text-secondary" />
        )}
        <Icon className="w-4 h-4 text-accent" />
        <span className="text-sm font-medium text-text-primary">{title}</span>
      </button>
      {isOpen && <div className="p-3 border-t border-border bg-page/50">{children}</div>}
    </div>
  )
}

export default function ArtifactModal({ artifactId, onClose }: ArtifactModalProps) {
  const [artifact, setArtifact] = useState<ArtifactWithContent | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const queryClient = useQueryClient()
  const { addToast } = useToast()

  useEffect(() => {
    setLoading(true)
    setError(null)

    api.artifact(artifactId)
      .then((data) => setArtifact(data as ArtifactWithContent))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [artifactId])

  // Fetch validation history for decisions
  const { data: validationHistory } = useQuery<ValidationEvent[]>({
    queryKey: ['validation-history', artifactId],
    queryFn: async () => {
      const res = await fetch(`/api/artifacts?type=decision_validation&search=${artifactId}&limit=20`)
      if (!res.ok) return []
      const data = await res.json()
      return data.artifacts.map((a: Artifact & { content?: Record<string, unknown> }) => ({
        id: a.id,
        timestamp: a.created_at,
        ...a.content,
      }))
    },
    enabled: artifact?.type === 'decision',
  })

  // Fetch related artifacts (by tags)
  const { data: relatedArtifacts } = useQuery<Artifact[]>({
    queryKey: ['related-artifacts', artifactId, artifact?.tags],
    queryFn: async () => {
      if (!artifact?.tags || artifact.tags.length === 0) return []
      // Search by first few tags
      const searchTag = artifact.tags[0]
      const res = await fetch(`/api/artifacts?search=${encodeURIComponent(searchTag)}&limit=6`)
      if (!res.ok) return []
      const data = await res.json()
      // Filter out the current artifact
      return data.artifacts.filter((a: Artifact) => a.id !== artifactId)
    },
    enabled: !!artifact?.tags && artifact.tags.length > 0,
  })

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])

  const handleCopy = () => {
    if (artifact?.content) {
      navigator.clipboard.writeText(JSON.stringify(artifact.content, null, 2))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      const res = await fetch(`/api/artifacts/${artifactId}`, { method: 'DELETE' })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to delete')
      }
      queryClient.invalidateQueries({ queryKey: ['artifacts'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      addToast({ type: 'success', title: 'Artifact deleted', message: artifact?.title || artifactId })
      onClose()
    } catch (e) {
      addToast({ type: 'error', title: 'Delete failed', message: (e as Error).message })
    } finally {
      setDeleting(false)
      setShowDeleteConfirm(false)
    }
  }

  const colorClasses = artifact
    ? (typeColors[artifact.type] || 'bg-gray-500/20 text-gray-400 border-gray-500/30')
    : ''

  const title = artifact?.title ?? artifact?.id ?? ''
  const content = artifact?.content
  const contentStr = content ? JSON.stringify(content, null, 2) : null

  // Extract key fields for structured display
  const keyFields = content && typeof content === 'object' ? {
    // Facts
    claim: (content as Record<string, unknown>).claim,
    confidence: (content as Record<string, unknown>).confidence,
    provenance: (content as Record<string, unknown>).provenance,
    // Decisions
    decision: (content as Record<string, unknown>).decision,
    rationale: (content as Record<string, unknown>).rationale,
    alternatives: (content as Record<string, unknown>).alternatives,
    outcome_status: (content as Record<string, unknown>).outcome_status,
    // Episodes
    goal: (content as Record<string, unknown>).goal,
    result: (content as Record<string, unknown>).result,
    result_summary: (content as Record<string, unknown>).result_summary,
    // Evaluations
    grade: (content as Record<string, unknown>).grade,
    rubric: (content as Record<string, unknown>).rubric,
  } : null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative bg-card border border-border rounded-lg w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            {artifact && (
              <span className={`text-xs font-mono uppercase px-1.5 py-0.5 rounded border ${colorClasses}`}>
                {artifact.type.replace('_', ' ')}
              </span>
            )}
            <span className="text-sm font-medium text-text-secondary">Artifact Detail</span>
          </div>
          <div className="flex items-center gap-2">
            {contentStr && (
              <button
                onClick={handleCopy}
                className="p-1.5 rounded hover:bg-white/10 text-text-secondary hover:text-text-primary transition-colors"
                title="Copy JSON"
              >
                {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-white/10 text-text-secondary hover:text-text-primary transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="space-y-3 animate-pulse">
              <div className="h-6 w-3/4 bg-border rounded" />
              <div className="h-4 w-1/2 bg-border rounded" />
              <div className="h-32 bg-border rounded mt-4" />
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-error text-sm bg-error/10 p-3 rounded">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          {!loading && !error && artifact && (
            <div className="space-y-4">
              {/* Title */}
              <h2 className="text-lg font-display font-semibold text-text-primary">
                {title}
              </h2>

              {/* Metadata */}
              <div className="flex flex-wrap gap-4 text-xs text-text-secondary">
                <div className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  <span>{formatDateTime(artifact.created_at)}</span>
                  <span className="text-text-secondary/50">({formatRelativeTime(artifact.created_at)})</span>
                </div>
                <div className="flex items-center gap-1">
                  <Shield className="w-3 h-3" />
                  <span className={artifact.sensitivity === 'sensitive' ? 'text-warning' : ''}>
                    {artifact.sensitivity}
                  </span>
                </div>
                {artifact.source_workflow && (
                  <div className="flex items-center gap-1">
                    <ExternalLink className="w-3 h-3" />
                    <span>{artifact.source_workflow}</span>
                  </div>
                )}
              </div>

              {/* Tags */}
              {artifact.tags && artifact.tags.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <Tag className="w-3 h-3 text-text-secondary" />
                  {artifact.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-xs px-2 py-0.5 bg-accent-dim rounded text-accent"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {/* Key Fields (Structured View) */}
              {keyFields && Object.entries(keyFields).some(([, v]) => v !== undefined) && (
                <CollapsibleSection title="Key Fields" icon={Sparkles} defaultOpen={true}>
                  <div className="space-y-3">
                    {keyFields.claim != null && (
                      <div>
                        <div className="text-xs text-text-secondary uppercase mb-1">Claim</div>
                        <p className="text-sm text-text-primary">{String(keyFields.claim)}</p>
                      </div>
                    )}
                    {keyFields.decision != null && (
                      <div>
                        <div className="text-xs text-text-secondary uppercase mb-1">Decision</div>
                        <p className="text-sm text-text-primary">{String(keyFields.decision)}</p>
                      </div>
                    )}
                    {keyFields.goal != null && (
                      <div>
                        <div className="text-xs text-text-secondary uppercase mb-1">Goal</div>
                        <p className="text-sm text-text-primary">{String(keyFields.goal)}</p>
                      </div>
                    )}
                    {keyFields.rationale != null && (
                      <div>
                        <div className="text-xs text-text-secondary uppercase mb-1">Rationale</div>
                        <p className="text-sm text-text-primary">{String(keyFields.rationale)}</p>
                      </div>
                    )}
                    {keyFields.confidence != null && (
                      <div className="flex items-center gap-4">
                        <div>
                          <div className="text-xs text-text-secondary uppercase mb-1">Confidence</div>
                          <span className="text-sm font-mono text-accent">
                            {(Number(keyFields.confidence) * 100).toFixed(0)}%
                          </span>
                        </div>
                        {keyFields.outcome_status != null && (
                          <div>
                            <div className="text-xs text-text-secondary uppercase mb-1">Status</div>
                            <span className={`text-sm font-mono ${
                              String(keyFields.outcome_status) === 'validated' ? 'text-green-400' :
                              String(keyFields.outcome_status) === 'reversed' ? 'text-red-400' :
                              'text-warning'
                            }`}>
                              {String(keyFields.outcome_status)}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                    {keyFields.grade != null && (
                      <div className="flex items-center gap-4">
                        <div>
                          <div className="text-xs text-text-secondary uppercase mb-1">Grade</div>
                          <span className="text-2xl font-bold text-accent">{String(keyFields.grade)}</span>
                        </div>
                      </div>
                    )}
                    {keyFields.result != null && (
                      <div>
                        <div className="text-xs text-text-secondary uppercase mb-1">Result</div>
                        <span className={`text-sm px-2 py-0.5 rounded ${
                          String(keyFields.result) === 'success' ? 'bg-green-500/20 text-green-400' :
                          String(keyFields.result) === 'partial' ? 'bg-warning/20 text-warning' :
                          'bg-red-500/20 text-red-400'
                        }`}>
                          {String(keyFields.result)}
                        </span>
                        {keyFields.result_summary != null && (
                          <p className="text-sm text-text-secondary mt-1">{String(keyFields.result_summary)}</p>
                        )}
                      </div>
                    )}
                    {Array.isArray(keyFields.alternatives) && keyFields.alternatives.length > 0 && (
                      <div>
                        <div className="text-xs text-text-secondary uppercase mb-1">Alternatives Considered</div>
                        <ul className="text-sm text-text-secondary list-disc list-inside">
                          {keyFields.alternatives.map((alt: unknown, i: number) => (
                            <li key={i}>{String(alt)}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </CollapsibleSection>
              )}

              {/* Validation History (for decisions) */}
              {artifact.type === 'decision' && validationHistory && validationHistory.length > 0 && (
                <CollapsibleSection title="Validation History" icon={History} defaultOpen={false}>
                  <div className="space-y-3">
                    {validationHistory.map((event) => (
                      <div key={event.id} className="border-l-2 border-accent pl-3 py-1">
                        <div className="flex items-center gap-2 text-xs">
                          <span className={`px-1.5 py-0.5 rounded ${
                            event.status === 'validated' ? 'bg-green-500/20 text-green-400' :
                            event.status === 'reversed' ? 'bg-red-500/20 text-red-400' :
                            'bg-gray-500/20 text-gray-400'
                          }`}>
                            {event.status}
                          </span>
                          {event.result && (
                            <span className="text-text-secondary">{event.result}</span>
                          )}
                          <span className="text-text-secondary/50">{formatRelativeTime(event.timestamp)}</span>
                        </div>
                        {event.actual_outcome && (
                          <p className="text-xs text-text-secondary mt-1">{event.actual_outcome}</p>
                        )}
                        {event.confidence_delta && (
                          <span className={`text-xs ${event.confidence_delta > 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {event.confidence_delta > 0 ? '+' : ''}{event.confidence_delta}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </CollapsibleSection>
              )}

              {/* Related Artifacts */}
              {relatedArtifacts && relatedArtifacts.length > 0 && (
                <CollapsibleSection title="Related Artifacts" icon={Network} defaultOpen={false}>
                  <div className="space-y-2">
                    {relatedArtifacts.slice(0, 5).map((related) => (
                      <div
                        key={related.id}
                        className="flex items-center gap-2 p-2 bg-card border border-border rounded hover:border-accent/30 cursor-pointer transition-colors group"
                        onClick={() => {
                          // Navigate to related artifact
                          setArtifact(null)
                          setLoading(true)
                          api.artifact(related.id)
                            .then((data) => setArtifact(data as ArtifactWithContent))
                            .catch((e: Error) => setError(e.message))
                            .finally(() => setLoading(false))
                        }}
                      >
                        <span className={`text-xs font-mono uppercase px-1 py-0.5 rounded border ${typeColors[related.type] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'}`}>
                          {related.type.replace('_', ' ')}
                        </span>
                        <span className="text-xs text-text-primary truncate flex-1">
                          {related.title || related.id}
                        </span>
                        <ArrowRight className="w-3 h-3 text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    ))}
                  </div>
                </CollapsibleSection>
              )}

              {/* Raw JSON */}
              {contentStr && (
                <CollapsibleSection title="Raw JSON" icon={Link2} defaultOpen={false}>
                  <div className="bg-page border border-border rounded p-3 text-xs font-mono overflow-x-auto max-h-96">
                    {highlightJSON(contentStr)}
                  </div>
                </CollapsibleSection>
              )}

              {/* Footer */}
              <div className="pt-4 border-t border-border">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-text-secondary">
                    <span className="opacity-50">ID:</span>{' '}
                    <code className="font-mono bg-page px-1.5 py-0.5 rounded">{artifact.id}</code>
                  </div>
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 rounded transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete
                  </button>
                </div>

                {/* Delete Confirmation */}
                {showDeleteConfirm && (
                  <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-sm text-red-400 mb-3">
                      Delete this {artifact.type}? This cannot be undone.
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={handleDelete}
                        disabled={deleting}
                        className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-red-500 text-white rounded text-sm font-medium hover:bg-red-600 transition-colors disabled:opacity-50"
                      >
                        {deleting ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                        {deleting ? 'Deleting...' : 'Yes, delete'}
                      </button>
                      <button
                        onClick={() => setShowDeleteConfirm(false)}
                        disabled={deleting}
                        className="flex-1 px-3 py-2 bg-card border border-border rounded text-sm text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
