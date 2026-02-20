import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import QuickActions from './QuickActions'

export default function Layout() {
  return (
    <div className="h-screen flex bg-page">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0">
        <Header />

        <main className="flex-1 overflow-hidden p-6">
          <Outlet />
        </main>
      </div>

      <QuickActions />
    </div>
  )
}
