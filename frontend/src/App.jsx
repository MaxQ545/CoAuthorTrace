import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import AuthorPage from './pages/AuthorPage'
import NetworkPage from './pages/NetworkPage'
import RankingPage from './pages/RankingPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/author/:authorId" element={<AuthorPage />} />
        <Route path="/network" element={<NetworkPage />} />
        <Route path="/network/:authorId" element={<NetworkPage />} />
        <Route path="/ranking" element={<RankingPage />} />
      </Routes>
    </Layout>
  )
}

export default App
