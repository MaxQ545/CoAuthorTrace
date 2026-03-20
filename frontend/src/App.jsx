import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import { usePageTracking } from './hooks/usePageTracking'

const HomePage = lazy(() => import('./pages/HomePage'))
const AuthorPage = lazy(() => import('./pages/AuthorPage'))
const AuthorSearchPage = lazy(() => import('./pages/AuthorSearchPage'))
const NetworkPage = lazy(() => import('./pages/NetworkPage'))
const RankingPage = lazy(() => import('./pages/RankingPage'))
const AdminLoginPage = lazy(() => import('./pages/AdminLoginPage'))
const AdminDashboardPage = lazy(() => import('./pages/AdminDashboardPage'))
const ComparePage = lazy(() => import('./pages/ComparePage'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-sm text-muted-foreground">Loading...</span>
      </div>
    </div>
  )
}

function App() {
  usePageTracking()

  return (
    <Layout>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/authors/search" element={<AuthorSearchPage />} />
          <Route path="/author/:authorId" element={<AuthorPage />} />
          <Route path="/network" element={<NetworkPage />} />
          <Route path="/network/:authorId" element={<NetworkPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/ranking" element={<RankingPage />} />
          <Route path="/admin/login" element={<AdminLoginPage />} />
          <Route path="/admin" element={<AdminDashboardPage />} />
        </Routes>
      </Suspense>
    </Layout>
  )
}

export default App
