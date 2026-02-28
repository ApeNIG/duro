import { RefreshCw, Menu } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import Heartbeat from './Heartbeat'
import { useLocation } from 'react-router-dom'

interface HeaderProps {
  onMenuClick?: () => void
}

export default function Header({ onMenuClick }: HeaderProps) {
  const queryClient = useQueryClient()
  const location = useLocation()

  const handleRefresh = () => {
    queryClient.invalidateQueries()
  }

  // Get current page name from path
  const currentPage = location.pathname.split('/').filter(Boolean)[0] || 'overview'

  return (
    <header className="h-10 px-4 lg:px-6 flex items-center justify-between border-b border-border bg-bg-void">
      <div className="flex items-center gap-3">
        {/* Hamburger menu - mobile only */}
        <button
          onClick={onMenuClick}
          className="lg:hidden p-1 hover:bg-bg-active text-text-secondary hover:text-accent transition-colors"
        >
          <Menu className="w-4 h-4" />
        </button>

        {/* Terminal-style breadcrumb */}
        <div className="font-mono text-xs text-text-muted">
          <span className="text-text-dim">~/duro/</span>
          <span className="text-text-secondary">{currentPage}</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <Heartbeat />

        <button
          onClick={handleRefresh}
          className="p-1 hover:bg-bg-active text-text-muted hover:text-accent transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>
    </header>
  )
}
