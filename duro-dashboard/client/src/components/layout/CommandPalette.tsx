import { Command } from 'cmdk'
import { useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity, Database, Search, CheckCircle, ArrowUpCircle,
  Target, Layers, AlertTriangle, Lightbulb, Link2, GitBranch,
  Settings, Shield, Heart, Zap, Clock, Command as CommandIcon
} from 'lucide-react'
import { useUIStore } from '@/store/uiStore'

const pages = [
  { name: 'Overview', path: '/overview', icon: Activity, section: 'Command Center' },
  { name: 'Activity Feed', path: '/activity', icon: Zap, section: 'Command Center' },
  { name: 'Memory Browser', path: '/memory', icon: Database, section: 'Knowledge' },
  { name: 'Knowledge Graph', path: '/relationships', icon: GitBranch, section: 'Knowledge' },
  { name: 'Search', path: '/search', icon: Search, section: 'Knowledge' },
  { name: 'Insights & Health', path: '/insights', icon: Lightbulb, section: 'Intelligence' },
  { name: 'Episodes Timeline', path: '/episodes', icon: Target, section: 'Intelligence' },
  { name: 'Skills Library', path: '/skills', icon: Layers, section: 'Intelligence' },
  { name: 'Emergence', path: '/emergence', icon: Link2, section: 'Intelligence' },
  { name: 'Decision Reviews', path: '/reviews', icon: CheckCircle, section: 'Governance' },
  { name: 'Promotions Pipeline', path: '/promotions', icon: ArrowUpCircle, section: 'Governance' },
  { name: 'Incident RCAs', path: '/incidents', icon: AlertTriangle, section: 'Governance' },
  { name: 'Change Ledger', path: '/changes', icon: Clock, section: 'Governance' },
  { name: 'Security Center', path: '/security', icon: Shield, section: 'Security' },
  { name: 'Health & Maintenance', path: '/health', icon: Heart, section: 'Security' },
  { name: 'Settings', path: '/settings', icon: Settings, section: 'System' },
]

const quickActions = [
  { name: 'Store Fact', action: 'store-fact', icon: Database },
  { name: 'Create Episode', action: 'create-episode', icon: Target },
  { name: 'Store Decision', action: 'store-decision', icon: CheckCircle },
  { name: 'Run Health Check', action: 'health-check', icon: Heart },
]

export default function CommandPalette() {
  const navigate = useNavigate()
  const { commandPaletteOpen, closeCommandPalette, toggleCommandPalette } = useUIStore()

  // Keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        toggleCommandPalette()
      }
      if (e.key === 'Escape' && commandPaletteOpen) {
        closeCommandPalette()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [commandPaletteOpen, toggleCommandPalette, closeCommandPalette])

  const handleSelect = useCallback((path: string) => {
    navigate(path)
    closeCommandPalette()
  }, [navigate, closeCommandPalette])

  const handleAction = useCallback((action: string) => {
    // TODO: Implement quick actions
    console.log('Quick action:', action)
    closeCommandPalette()
  }, [closeCommandPalette])

  // Group pages by section
  const groupedPages = pages.reduce((acc, page) => {
    if (!acc[page.section]) acc[page.section] = []
    acc[page.section].push(page)
    return acc
  }, {} as Record<string, typeof pages>)

  return (
    <AnimatePresence>
      {commandPaletteOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={closeCommandPalette}
          />

          {/* Command Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-2xl px-4 z-50"
          >
            <Command
              className="bg-bg-elevated border border-glass-border rounded-xl shadow-2xl overflow-hidden"
              loop
            >
              <div className="flex items-center gap-3 px-4 py-3 border-b border-glass-border">
                <CommandIcon className="w-5 h-5 text-neon-cyan" />
                <Command.Input
                  placeholder="Search pages, actions, or artifacts..."
                  className="flex-1 bg-transparent border-none text-text-primary placeholder:text-text-muted outline-none text-base"
                  autoFocus
                />
                <kbd className="hidden sm:flex items-center gap-1 px-2 py-1 text-xs text-text-muted bg-bg-card rounded border border-glass-border">
                  ESC
                </kbd>
              </div>

              <Command.List className="max-h-[400px] overflow-y-auto p-2">
                <Command.Empty className="py-8 text-center text-text-muted">
                  No results found.
                </Command.Empty>

                {/* Quick Actions */}
                <Command.Group heading="Quick Actions">
                  {quickActions.map((action) => (
                    <Command.Item
                      key={action.action}
                      value={action.name}
                      onSelect={() => handleAction(action.action)}
                      className="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer text-text-secondary data-[selected=true]:bg-accent-dim data-[selected=true]:text-accent transition-colors"
                    >
                      <action.icon className="w-4 h-4" />
                      <span>{action.name}</span>
                      <span className="ml-auto text-xs text-text-muted">Action</span>
                    </Command.Item>
                  ))}
                </Command.Group>

                {/* Pages by Section */}
                {Object.entries(groupedPages).map(([section, sectionPages]) => (
                  <Command.Group key={section} heading={section}>
                    {sectionPages.map((page) => (
                      <Command.Item
                        key={page.path}
                        value={`${page.name} ${section}`}
                        onSelect={() => handleSelect(page.path)}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer text-text-secondary data-[selected=true]:bg-accent-dim data-[selected=true]:text-accent transition-colors"
                      >
                        <page.icon className="w-4 h-4" />
                        <span>{page.name}</span>
                        <span className="ml-auto text-xs text-text-muted">{section}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                ))}
              </Command.List>

              {/* Footer */}
              <div className="flex items-center justify-between px-4 py-2 border-t border-glass-border text-xs text-text-muted">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-bg-card rounded border border-glass-border">↑↓</kbd>
                    navigate
                  </span>
                  <span className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-bg-card rounded border border-glass-border">↵</kbd>
                    select
                  </span>
                </div>
                <span className="flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 bg-bg-card rounded border border-glass-border">⌘</kbd>
                  <kbd className="px-1.5 py-0.5 bg-bg-card rounded border border-glass-border">K</kbd>
                  toggle
                </span>
              </div>
            </Command>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
