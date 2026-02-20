import { useEffect, useState } from 'react'
import { X, ExternalLink, Clock, Tag, Shield } from 'lucide-react'
import { api } from '@/lib/api'
import type { Artifact } from '@/lib/api'

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
}

interface ArtifactWithContent extends Artifact {
  content?: Record<string, unknown> | string | null
}

function formatDateTime(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatContent(content: Record<string, unknown> | string | null | undefined): string {
  if (!content) return ''
  if (typeof content === 'string') return content
  return JSON.stringify(content, null, 2)
}

export default function ArtifactModal({ artifactId, onClose }: ArtifactModalProps) {
  const [artifact, setArtifact] = useState<ArtifactWithContent | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)

    api.artifact(artifactId)
      .then((data) => setArtifact(data as ArtifactWithContent))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [artifactId])

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])

  const colorClasses = artifact
    ? (typeColors[artifact.type] || 'bg-gray-500/20 text-gray-400 border-gray-500/30')
    : ''

  const title = artifact?.title ?? artifact?.id ?? ''
  const contentStr = artifact?.content ? formatContent(artifact.content) : null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative bg-card border border-border rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            {artifact && (
              <span className={`text-xs font-mono uppercase px-1.5 py-0.5 rounded border ${colorClasses}`}>
                {artifact.type}
              </span>
            )}
            <span className="text-sm font-medium text-text-secondary">Artifact Detail</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-white/10 text-text-secondary hover:text-text-primary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="space-y-3 animate-pulse">
              <div className="h-6 w-3/4 bg-border rounded" />
              <div className="h-4 w-1/2 bg-border rounded" />
              <div className="h-32 bg-border rounded mt-4" />
            </div>
          )}

          {error && <div className="text-error text-sm">{error}</div>}

          {!loading && !error && artifact && (
            <div className="space-y-4">
              <h2 className="text-lg font-display font-semibold text-text-primary">
                {title}
              </h2>

              <div className="flex flex-wrap gap-4 text-xs text-text-secondary">
                <div className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  <span>{formatDateTime(artifact.created_at)}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Shield className="w-3 h-3" />
                  <span>{artifact.sensitivity}</span>
                </div>
                {artifact.source_workflow && (
                  <div className="flex items-center gap-1">
                    <ExternalLink className="w-3 h-3" />
                    <span>{artifact.source_workflow}</span>
                  </div>
                )}
              </div>

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

              {contentStr && (
                <div className="mt-4">
                  <div className="text-xs text-text-secondary uppercase tracking-wider mb-2">
                    Content
                  </div>
                  <pre className="bg-page border border-border rounded p-3 text-xs font-mono overflow-x-auto text-text-primary whitespace-pre-wrap">
                    {contentStr}
                  </pre>
                </div>
              )}

              <div className="pt-4 border-t border-border">
                <div className="text-xs text-text-secondary">
                  <span className="opacity-50">ID:</span>{' '}
                  <code className="font-mono">{artifact.id}</code>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
