import { NavLink } from 'react-router-dom'
import {
  X,
  LayoutDashboard,
  Activity,
  Lightbulb,
  Database,
  Search,
  GitBranch,
  PlayCircle,
  CheckSquare,
  TrendingUp,
  HeartPulse,
  Shield,
  AlertTriangle,
  Clock,
  Zap,
  Settings,
  LucideIcon
} from 'lucide-react'
import { useHealth, usePendingReviews } from '@/hooks/useStats'

interface NavItemProps {
  to: string
  label: string
  icon: LucideIcon
  badge?: number
  onClick?: () => void
}

function NavItem({ to, label, icon: Icon, badge, onClick }: NavItemProps) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive }) =>
        `w-full flex items-center gap-2.5 px-2 py-1.5 text-xs font-mono transition-all ${
          isActive
            ? 'bg-accent/10 text-accent border-l-2 border-accent -ml-[2px] pl-[10px]'
            : 'text-text-secondary hover:text-text-primary hover:bg-white/5'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? 'text-accent' : 'text-text-muted'}`} />
          <span>{label}</span>
          {badge !== undefined && badge > 0 && (
            <span className="ml-auto px-1.5 py-0.5 text-[10px] bg-warning/20 text-warning rounded-full font-medium">
              {badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-2 py-2 text-[10px] font-mono text-text-muted">
      {children}
    </div>
  )
}

interface SidebarProps {
  onClose?: () => void
}

export default function Sidebar({ onClose }: SidebarProps) {
  const { data: health } = useHealth()
  const { data: pendingCount } = usePendingReviews()

  return (
    <aside className="w-[200px] h-full bg-bg-void flex flex-col border-r border-border">
      {/* Logo - lowercase, minimal */}
      <div className="h-12 px-4 flex items-center justify-between">
        <span className="font-mono text-sm font-medium text-accent">duro</span>
        {/* Close button - mobile only */}
        <button
          onClick={onClose}
          className="lg:hidden p-1 hover:bg-white/10 transition-colors"
        >
          <X className="w-4 h-4 text-text-secondary" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-2 overflow-y-auto">
        <SectionLabel># command</SectionLabel>
        <div className="space-y-0.5">
          <NavItem to="/overview" label="overview" icon={LayoutDashboard} onClick={onClose} />
          <NavItem to="/activity" label="activity" icon={Activity} onClick={onClose} />
          <NavItem to="/insights" label="insights" icon={Lightbulb} onClick={onClose} />
        </div>

        <SectionLabel># knowledge</SectionLabel>
        <div className="space-y-0.5">
          <NavItem to="/memory" label="memory" icon={Database} onClick={onClose} />
          <NavItem to="/search" label="search" icon={Search} onClick={onClose} />
          <NavItem to="/relationships" label="graph" icon={GitBranch} onClick={onClose} />
        </div>

        <SectionLabel># workflows</SectionLabel>
        <div className="space-y-0.5">
          <NavItem to="/episodes" label="episodes" icon={PlayCircle} onClick={onClose} />
          <NavItem to="/reviews" label="reviews" icon={CheckSquare} badge={pendingCount} onClick={onClose} />
          <NavItem to="/promotions" label="promotions" icon={TrendingUp} onClick={onClose} />
        </div>

        <SectionLabel># system</SectionLabel>
        <div className="space-y-0.5">
          <NavItem to="/health" label="health" icon={HeartPulse} onClick={onClose} />
          <NavItem to="/security" label="security" icon={Shield} onClick={onClose} />
          <NavItem to="/incidents" label="incidents" icon={AlertTriangle} onClick={onClose} />
          <NavItem to="/changes" label="changes" icon={Clock} onClick={onClose} />
          <NavItem to="/skills" label="skills" icon={Zap} onClick={onClose} />
          <NavItem to="/settings" label="settings" icon={Settings} onClick={onClose} />
        </div>
      </nav>

      {/* System Status - minimal */}
      <div className="px-4 py-3 border-t border-border">
        <div className="flex items-center gap-2 text-[10px] font-mono">
          <span className={`w-1.5 h-1.5 rounded-full ${
            health?.database === 'connected' ? 'bg-accent' : 'bg-error'
          }`} />
          <span className={health?.database === 'connected' ? 'text-accent' : 'text-error'}>
            {health?.database === 'connected' ? 'connected' : 'disconnected'}
          </span>
        </div>
      </div>
    </aside>
  )
}
