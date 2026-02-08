import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import AuthorPage from './pages/AuthorPage'
import AuthorSearchPage from './pages/AuthorSearchPage'
import NetworkPage from './pages/NetworkPage'
import RankingPage from './pages/RankingPage'
import AdminLoginPage from './pages/AdminLoginPage'
import AdminDashboardPage from './pages/AdminDashboardPage'
import { usePageTracking } from './hooks/usePageTracking'

function App() {
  usePageTracking()

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/authors/search" element={<AuthorSearchPage />} />
        <Route path="/author/:authorId" element={<AuthorPage />} />
        <Route path="/network" element={<NetworkPage />} />
        <Route path="/network/:authorId" element={<NetworkPage />} />
        <Route path="/ranking" element={<RankingPage />} />
        <Route path="/admin/login" element={<AdminLoginPage />} />
        <Route path="/admin" element={<AdminDashboardPage />} />
      </Routes>
    </Layout>
  )
}

export default App
