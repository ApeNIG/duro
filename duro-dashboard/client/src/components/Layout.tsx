import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import QuickActions from './QuickActions'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Global keyboard shortcuts
  useKeyboardShortcuts({
    onEscape: () => setSidebarOpen(false),
  })

  return (
    <div className="h-screen flex bg-page">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar - hidden on mobile, shown on lg+ */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 transform transition-transform duration-200 ease-in-out
          lg:relative lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <Header onMenuClick={() => setSidebarOpen(true)} />

        <main className="flex-1 overflow-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>

      <QuickActions />
    </div>
  )
}
