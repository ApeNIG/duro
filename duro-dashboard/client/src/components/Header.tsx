import { RefreshCw, Sun, Moon } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import Heartbeat from './Heartbeat'
import NotificationCenter from './NotificationCenter'
import { useTheme } from './ThemeProvider'

export default function Header() {
  const queryClient = useQueryClient()
  const { theme, toggleTheme } = useTheme()

  const handleRefresh = () => {
    queryClient.invalidateQueries()
  }

  return (
    <header className="h-14 px-6 flex items-center justify-between border-b border-border bg-card">
      <div className="flex items-center gap-4">
        <h1 className="font-display font-semibold text-lg tracking-tight">
          <span className="text-accent">DURO</span>
          <span className="text-text-secondary ml-2 text-sm font-normal">Dashboard</span>
        </h1>
      </div>

      <div className="flex items-center gap-4">
        <Heartbeat />

        <NotificationCenter />

        <button
          onClick={toggleTheme}
          className="p-1.5 rounded hover:bg-accent-dim text-text-secondary hover:text-accent transition-colors"
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        <button
          onClick={handleRefresh}
          className="p-1.5 rounded hover:bg-accent-dim text-text-secondary hover:text-accent transition-colors"
          title="Refresh all data"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
