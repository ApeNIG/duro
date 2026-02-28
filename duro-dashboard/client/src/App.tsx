import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Memory from './pages/Memory'
import Activity from './pages/Activity'
import Settings from './pages/Settings'
import Reviews from './pages/Reviews'
import Promotions from './pages/Promotions'
import Relationships from './pages/Relationships'
import Episodes from './pages/Episodes'
import Skills from './pages/Skills'
import Incidents from './pages/Incidents'
import Search from './pages/Search'
import Insights from './pages/Insights'
import Suggestions from './pages/Suggestions'
import Security from './pages/Security'
import Health from './pages/Health'
import Changes from './pages/Changes'
import Emergence from './pages/Emergence'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        {/* Command Center */}
        <Route path="overview" element={<Overview />} />
        <Route path="activity" element={<Activity />} />
        {/* Knowledge */}
        <Route path="memory" element={<Memory />} />
        <Route path="relationships" element={<Relationships />} />
        <Route path="search" element={<Search />} />
        {/* Intelligence */}
        <Route path="insights" element={<Insights />} />
        <Route path="episodes" element={<Episodes />} />
        <Route path="skills" element={<Skills />} />
        <Route path="emergence" element={<Emergence />} />
        <Route path="suggestions" element={<Suggestions />} />
        {/* Governance */}
        <Route path="reviews" element={<Reviews />} />
        <Route path="promotions" element={<Promotions />} />
        <Route path="incidents" element={<Incidents />} />
        <Route path="changes" element={<Changes />} />
        {/* Security */}
        <Route path="security" element={<Security />} />
        <Route path="health" element={<Health />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
