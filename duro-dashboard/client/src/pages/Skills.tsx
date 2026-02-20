import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Code,
  Loader2,
  CheckCircle,
  TrendingUp,
  Clock,
  ChevronRight,
  Sparkles,
  Beaker,
  Layers,
} from 'lucide-react'

interface SkillStats {
  total_uses: number
  successes: number
  failures: number
  success_rate: number
  last_used?: string
  avg_duration_ms?: number
}

interface Skill {
  id: string
  name: string
  description: string
  category: string
  is_core: boolean
  tested: boolean
  tags: string[]
  stats?: SkillStats
  code?: string
}

interface SkillsResponse {
  skills: Skill[]
  total: number
  categories: string[]
}

function formatLastUsed(isoString: string | undefined): string {
  if (!isoString) return 'Never'
  const date = new Date(isoString)
  const now = new Date()
  const days = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  return date.toLocaleDateString()
}

function SkillCard({
  skill,
  onSelect,
}: {
  skill: Skill
  onSelect: (id: string) => void
}) {
  const successRate = skill.stats?.success_rate || 0
  const totalUses = skill.stats?.total_uses || 0

  return (
    <div
      className="bg-card border border-border rounded-lg p-4 cursor-pointer hover:border-accent/30 transition-colors"
      onClick={() => onSelect(skill.id)}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
            skill.is_core
              ? 'bg-accent/20 text-accent'
              : 'bg-white/5 text-text-secondary'
          }`}
        >
          {skill.is_core ? (
            <Sparkles className="w-5 h-5" />
          ) : (
            <Code className="w-5 h-5" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-medium text-text-primary truncate">
              {skill.name}
            </h3>
            {skill.tested && (
              <CheckCircle className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />
            )}
          </div>

          {/* Description */}
          <p className="text-xs text-text-secondary line-clamp-2 mb-2">
            {skill.description || 'No description'}
          </p>

          {/* Stats */}
          <div className="flex items-center gap-3 text-xs">
            {totalUses > 0 && (
              <>
                <span className="text-text-secondary">
                  {totalUses} uses
                </span>
                <span
                  className={`flex items-center gap-1 ${
                    successRate >= 80
                      ? 'text-green-400'
                      : successRate >= 50
                      ? 'text-warning'
                      : 'text-red-400'
                  }`}
                >
                  <TrendingUp className="w-3 h-3" />
                  {successRate.toFixed(0)}%
                </span>
              </>
            )}
            {skill.stats?.last_used && (
              <span className="text-text-secondary flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatLastUsed(skill.stats.last_used)}
              </span>
            )}
          </div>

          {/* Category & Tags */}
          <div className="flex items-center gap-2 mt-2">
            <span className="text-xs px-1.5 py-0.5 bg-accent/10 text-accent rounded">
              {skill.category}
            </span>
            {skill.tags.slice(0, 2).map((tag) => (
              <span
                key={tag}
                className="text-xs px-1.5 py-0.5 bg-white/5 text-text-secondary rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        <ChevronRight className="w-5 h-5 text-text-secondary flex-shrink-0" />
      </div>
    </div>
  )
}

function SkillDetail({
  skillId,
  onClose,
}: {
  skillId: string
  onClose: () => void
}) {
  const { data: skill, isLoading } = useQuery<Skill>({
    queryKey: ['skill', skillId],
    queryFn: async () => {
      const res = await fetch(`/api/skills/${skillId}`)
      if (!res.ok) throw new Error('Failed to fetch skill')
      return res.json()
    },
    enabled: !!skillId,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-text-secondary" />
      </div>
    )
  }

  if (!skill) return null

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="text-text-secondary hover:text-text-primary"
          >
            ← Back
          </button>
          <h2 className="text-lg font-semibold text-text-primary">{skill.name}</h2>
          {skill.is_core && (
            <span className="text-xs px-2 py-0.5 bg-accent/20 text-accent rounded">
              Core
            </span>
          )}
          {skill.tested && (
            <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded flex items-center gap-1">
              <Beaker className="w-3 h-3" />
              Tested
            </span>
          )}
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-text-secondary mb-4">{skill.description}</p>

      {/* Stats */}
      {skill.stats && (
        <div className="grid grid-cols-4 gap-4 mb-4">
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-xs text-text-secondary uppercase">Uses</div>
            <div className="text-xl font-mono text-text-primary">
              {skill.stats.total_uses}
            </div>
          </div>
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-xs text-text-secondary uppercase">Success</div>
            <div className="text-xl font-mono text-green-400">
              {skill.stats.successes}
            </div>
          </div>
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-xs text-text-secondary uppercase">Failed</div>
            <div className="text-xl font-mono text-red-400">
              {skill.stats.failures}
            </div>
          </div>
          <div className="bg-card border border-border rounded-lg p-3">
            <div className="text-xs text-text-secondary uppercase">Rate</div>
            <div
              className={`text-xl font-mono ${
                skill.stats.success_rate >= 80
                  ? 'text-green-400'
                  : skill.stats.success_rate >= 50
                  ? 'text-warning'
                  : 'text-red-400'
              }`}
            >
              {skill.stats.success_rate.toFixed(0)}%
            </div>
          </div>
        </div>
      )}

      {/* Code */}
      {skill.code && (
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          <div className="flex items-center gap-2 text-xs text-text-secondary uppercase mb-2">
            <Code className="w-3.5 h-3.5" />
            Source Code
          </div>
          <div className="flex-1 overflow-auto bg-page border border-border rounded-lg">
            <pre className="p-4 text-xs text-text-primary font-mono whitespace-pre overflow-x-auto">
              {skill.code}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Skills() {
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null)
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [testedFilter, setTestedFilter] = useState<boolean | null>(null)

  const { data, isLoading } = useQuery<SkillsResponse>({
    queryKey: ['skills'],
    queryFn: async () => {
      const res = await fetch('/api/skills')
      if (!res.ok) throw new Error('Failed to fetch skills')
      return res.json()
    },
    refetchInterval: 30000,
  })

  const { data: stats } = useQuery({
    queryKey: ['skills-stats'],
    queryFn: async () => {
      const res = await fetch('/api/skills/stats/summary')
      if (!res.ok) throw new Error('Failed to fetch stats')
      return res.json()
    },
  })

  const skills = data?.skills || []
  const categories = data?.categories || []

  const filteredSkills = skills.filter((s) => {
    if (categoryFilter !== 'all' && s.category !== categoryFilter) return false
    if (testedFilter !== null && s.tested !== testedFilter) return false
    return true
  })

  const coreCount = skills.filter((s) => s.is_core).length
  const testedCount = skills.filter((s) => s.tested).length

  if (selectedSkill) {
    return (
      <div className="h-full">
        <SkillDetail
          skillId={selectedSkill}
          onClose={() => setSelectedSkill(null)}
        />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Layers className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-display font-semibold">Skill Library</h1>
          <span className="text-sm text-text-secondary">
            {skills.length} skills
          </span>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-3 py-1.5 text-sm bg-card border border-border rounded text-text-primary"
          >
            <option value="all">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>

          <button
            onClick={() =>
              setTestedFilter(testedFilter === true ? null : true)
            }
            className={`px-3 py-1.5 text-sm rounded transition-colors flex items-center gap-1 ${
              testedFilter === true
                ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                : 'text-text-secondary hover:text-text-primary border border-border'
            }`}
          >
            <Beaker className="w-3.5 h-3.5" />
            Tested
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Total</div>
          <div className="text-2xl font-mono text-text-primary">{skills.length}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Core</div>
          <div className="text-2xl font-mono text-accent">{coreCount}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Tested</div>
          <div className="text-2xl font-mono text-green-400">{testedCount}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary uppercase">Success Rate</div>
          <div className="text-2xl font-mono text-text-primary">
            {stats?.overall_success_rate?.toFixed(0) || '-'}%
          </div>
        </div>
      </div>

      {/* Skill Grid */}
      <div className="flex-1 overflow-auto min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-text-secondary" />
          </div>
        ) : filteredSkills.length === 0 ? (
          <div className="text-center py-12 text-text-secondary">
            No skills found
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filteredSkills.map((skill) => (
              <SkillCard
                key={skill.id}
                skill={skill}
                onSelect={setSelectedSkill}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
