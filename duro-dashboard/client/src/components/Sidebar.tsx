import { NavLink } from 'react-router-dom'
import { Database, Activity, Brain, Settings, Zap, CheckCircle, GitBranch, Target, Layers, AlertTriangle, Sparkles, Lightbulb } from 'lucide-react'
import { useHealth, usePendingReviews } from '@/hooks/useStats'

interface NavItemProps {
  to: string
  icon: React.ReactNode
  label: string
  badge?: number
}

function NavItem({ to, icon, label, badge }: NavItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `w-full flex items-center justify-between gap-3 px-3 py-2 rounded text-sm transition-colors ${
          isActive
            ? 'bg-accent-dim text-accent'
            : 'text-text-secondary hover:text-text-primary hover:bg-white/5'
        }`
      }
    >
      <div className="flex items-center gap-3">
        {icon}
        <span>{label}</span>
      </div>
      {badge !== undefined && badge > 0 && (
        <span className="px-1.5 py-0.5 text-xs bg-warning/20 text-warning rounded-full">
          {badge}
        </span>
      )}
    </NavLink>
  )
}

export default function Sidebar() {
  const { data: health } = useHealth()
  const { data: pendingCount } = usePendingReviews()

  return (
    <aside className="w-56 h-full bg-sidebar border-r border-border flex flex-col">
      {/* Logo */}
      <div className="h-14 px-4 flex items-center border-b border-border">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-accent" />
          <span className="font-display font-semibold tracking-tight">duro</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        <NavItem to="/overview" icon={<Activity className="w-4 h-4" />} label="Overview" />
        <NavItem to="/search" icon={<Sparkles className="w-4 h-4" />} label="Search" />
        <NavItem to="/memory" icon={<Database className="w-4 h-4" />} label="Memory" />
        <NavItem to="/activity" icon={<Zap className="w-4 h-4" />} label="Activity" />
        <NavItem to="/reviews" icon={<CheckCircle className="w-4 h-4" />} label="Reviews" badge={pendingCount} />
        <NavItem to="/episodes" icon={<Target className="w-4 h-4" />} label="Episodes" />
        <NavItem to="/skills" icon={<Layers className="w-4 h-4" />} label="Skills" />
        <NavItem to="/incidents" icon={<AlertTriangle className="w-4 h-4" />} label="Incidents" />
        <NavItem to="/insights" icon={<Lightbulb className="w-4 h-4" />} label="Insights" />
        <NavItem to="/relationships" icon={<GitBranch className="w-4 h-4" />} label="Graph" />
        <NavItem to="/settings" icon={<Settings className="w-4 h-4" />} label="Settings" />
      </nav>

      {/* System Status */}
      <div className="p-3 border-t border-border">
        <div className="bg-card rounded p-3 space-y-2">
          <div className="text-xs text-text-secondary uppercase tracking-wider">System</div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-text-secondary">Database</span>
              <span className={health?.database === 'connected' ? 'text-accent' : 'text-error'}>
                {health?.database || 'unknown'}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-text-secondary">Artifacts</span>
              <span className="text-text-primary font-mono">
                {health?.artifact_count?.toLocaleString() || '-'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
