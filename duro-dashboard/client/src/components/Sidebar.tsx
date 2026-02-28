import { NavLink } from 'react-router-dom'
import { X } from 'lucide-react'
import { useHealth, usePendingReviews } from '@/hooks/useStats'

interface NavItemProps {
  to: string
  label: string
  badge?: number
  onClick?: () => void
}

function NavItem({ to, label, badge, onClick }: NavItemProps) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive }) =>
        `w-full flex items-center gap-3 px-2.5 py-2 text-[13px] font-mono transition-colors ${
          isActive
            ? 'bg-bg-active text-accent'
            : 'text-text-secondary hover:text-text-primary'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <span className={`w-3 ${isActive ? 'text-accent' : 'text-text-muted'}`}>
            {isActive ? '>' : ' '}
          </span>
          <span>{label}</span>
          {badge !== undefined && badge > 0 && (
            <span className="ml-auto text-xs text-tag-episode">{badge}</span>
          )}
        </>
      )}
    </NavLink>
  )
}

interface SidebarProps {
  onClose?: () => void
}

export default function Sidebar({ onClose }: SidebarProps) {
  const { data: health } = useHealth()
  const { data: pendingCount } = usePendingReviews()

  return (
    <aside className="w-[220px] h-full bg-[#050708] flex flex-col border-r border-border">
      {/* Logo */}
      <div className="h-14 px-4 flex items-center justify-between">
        <div className="flex items-baseline gap-2">
          <span className="font-mono font-bold text-lg tracking-[4px] text-accent">DURO</span>
          <span className="font-mono text-[10px] text-text-muted">v2.0</span>
        </div>
        {/* Close button - mobile only */}
        <button
          onClick={onClose}
          className="lg:hidden p-1.5 hover:bg-white/10 rounded transition-colors"
        >
          <X className="w-5 h-5 text-text-secondary" />
        </button>
      </div>

      {/* Divider */}
      <div className="mx-4 h-px bg-border" />

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 overflow-y-auto">
        <div className="space-y-0.5">
          <NavItem to="/overview" label="overview" onClick={onClose} />
          <NavItem to="/activity" label="activity" onClick={onClose} />
        </div>

        <div className="my-4 mx-2 h-px bg-border" />

        <div className="space-y-0.5">
          <NavItem to="/memory" label="memory" onClick={onClose} />
          <NavItem to="/relationships" label="graph" onClick={onClose} />
          <NavItem to="/search" label="search" onClick={onClose} />
        </div>

        <div className="my-4 mx-2 h-px bg-border" />

        <div className="space-y-0.5">
          <NavItem to="/security" label="security" onClick={onClose} />
          <NavItem to="/health" label="health" onClick={onClose} />
        </div>

        <div className="my-4 mx-2 h-px bg-border" />

        <div className="space-y-0.5">
          <NavItem to="/reviews" label="reviews" badge={pendingCount} onClick={onClose} />
          <NavItem to="/incidents" label="incidents" onClick={onClose} />
          <NavItem to="/changes" label="changes" onClick={onClose} />
        </div>

        <div className="my-4 mx-2 h-px bg-border" />

        <div className="space-y-0.5">
          <NavItem to="/episodes" label="episodes" onClick={onClose} />
          <NavItem to="/skills" label="skills" onClick={onClose} />
          <NavItem to="/settings" label="settings" onClick={onClose} />
        </div>
      </nav>

      {/* System Status - minimal */}
      <div className="hidden sm:block px-4 py-3 border-t border-border">
        <div className="flex items-center gap-2 text-xs font-mono">
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
