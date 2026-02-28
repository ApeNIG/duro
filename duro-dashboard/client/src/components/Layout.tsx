import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import QuickActions from './QuickActions'
import CommandPalette from './layout/CommandPalette'
import { useUIStore } from '@/store/uiStore'

export default function Layout() {
  const { sidebarOpen, closeSidebar, openSidebar } = useUIStore()

  // Close sidebar on escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && sidebarOpen) {
        closeSidebar()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [sidebarOpen, closeSidebar])

  return (
    <div className="h-screen flex bg-bg-void relative z-10">
      {/* Command Palette */}
      <CommandPalette />

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={closeSidebar}
        />
      )}

      {/* Sidebar - hidden on mobile, shown on lg+ */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 transform transition-transform duration-300 ease-out
          lg:relative lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <Sidebar onClose={closeSidebar} />
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <Header onMenuClick={openSidebar} />

        <main className="flex-1 overflow-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>

      <QuickActions />
    </div>
  )
}
