import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Memory from './pages/Memory'
import Activity from './pages/Activity'
import Settings from './pages/Settings'
import Reviews from './pages/Reviews'
import Relationships from './pages/Relationships'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        <Route path="overview" element={<Overview />} />
        <Route path="memory" element={<Memory />} />
        <Route path="activity" element={<Activity />} />
        <Route path="reviews" element={<Reviews />} />
        <Route path="relationships" element={<Relationships />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
