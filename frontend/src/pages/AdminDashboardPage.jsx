import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { BarChart3, Bot, LogOut, AlertTriangle } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useAuth } from '../contexts/AuthContext'
import api from '../api/client'
import AnalyticsTab from '../components/admin/AnalyticsTab'
import CrawlTab from '../components/admin/CrawlTab'

export default function AdminDashboardPage() {
  const { isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const { data: systemStatus } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: () => api.getSystemStatus(),
    staleTime: 60 * 1000,
  })

  const redisDown = systemStatus?.redis_enabled && !systemStatus?.redis_connected

  const tab = searchParams.get('tab') || 'analytics'

  const handleTabChange = (value) => {
    setSearchParams({ tab: value }, { replace: true })
  }

  const handleLogout = () => {
    logout()
    navigate('/admin/login')
  }

  if (!isAuthenticated) {
    return <Navigate to="/admin/login" replace />
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6 pb-12">
      {/* Redis warning banner */}
      {redisDown && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-sm">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <span>缓存服务未连接，系统性能可能受影响 (Cache service not connected, system performance may be affected)</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Admin Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">System analytics and management</p>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-card hover:bg-muted transition text-sm"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>

      {/* Tabs */}
      <Tabs value={tab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="analytics" className="gap-2">
            <BarChart3 className="w-4 h-4" />
            Visitor Analytics
          </TabsTrigger>
          <TabsTrigger value="crawl" className="gap-2">
            <Bot className="w-4 h-4" />
            Crawl Management
          </TabsTrigger>
        </TabsList>

        <TabsContent value="analytics">
          <AnalyticsTab />
        </TabsContent>

        <TabsContent value="crawl">
          <CrawlTab />
        </TabsContent>
      </Tabs>
    </motion.div>
  )
}
