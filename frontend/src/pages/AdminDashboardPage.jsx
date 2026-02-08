import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  BarChart3, Bot, Eye, Globe, LogOut, RefreshCw, Play,
  Users, Calendar, TrendingUp, Activity, Plus, Trash2, Download,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import {
  useAdminAnalytics,
  useAdminCrawlStatus,
  useAdminCrawlTargets,
  useStartCrawl,
  useAddCrawlTarget,
  useDeleteCrawlTarget,
  useInitCrawlTargets,
  queryKeys,
} from '../hooks/queries'

// ---------------------------------------------------------------------------
// Status badge component
// ---------------------------------------------------------------------------
function StatusBadge({ status }) {
  const styles = {
    completed: 'bg-green-500/10 text-green-600 border-green-500/20',
    running: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    failed: 'bg-red-500/10 text-red-600 border-red-500/20',
    idle: 'bg-muted text-muted-foreground border-border',
  }
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full border ${styles[status] || styles.idle}`}>
      {status}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------
function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
          <Icon className="w-4.5 h-4.5 text-primary" />
        </div>
        <span className="text-sm text-muted-foreground">{label}</span>
      </div>
      <p className="text-2xl font-bold text-foreground">{value?.toLocaleString?.() ?? '-'}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Analytics Tab
// ---------------------------------------------------------------------------
function AnalyticsTab({ data }) {
  if (!data) return <p className="text-muted-foreground py-8 text-center">Loading analytics...</p>

  const { summary, daily_visits, top_pages, top_regions, recent_visits } = data

  return (
    <div className="space-y-8">
      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Eye} label="Total Visits" value={summary.total} />
        <StatCard icon={Users} label="Unique Visitors" value={summary.unique_ips} />
        <StatCard icon={Calendar} label="Today" value={summary.today} />
        <StatCard icon={TrendingUp} label="This Week" value={summary.this_week} />
      </div>

      {/* Daily visits table */}
      <Section title="Daily Visits (Last 30 Days)">
        {daily_visits.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-2 pr-4">Date</th>
                  <th className="pb-2 pr-4">Visits</th>
                  <th className="pb-2">Bar</th>
                </tr>
              </thead>
              <tbody>
                {daily_visits.map((d) => {
                  const max = Math.max(...daily_visits.map((x) => x.count), 1)
                  const pct = (d.count / max) * 100
                  return (
                    <tr key={d.date} className="border-b border-border/50">
                      <td className="py-1.5 pr-4 font-mono">{d.date}</td>
                      <td className="py-1.5 pr-4">{d.count}</td>
                      <td className="py-1.5">
                        <div className="h-4 rounded bg-primary/20" style={{ width: `${pct}%` }} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {/* Top pages & regions side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Section title="Top Pages">
          {top_pages.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <ul className="space-y-1.5 text-sm">
              {top_pages.slice(0, 10).map((p, i) => (
                <li key={i} className="flex justify-between">
                  <span className="truncate mr-2">{p.author_name ? `${p.path} (${p.author_name})` : p.path}</span>
                  <span className="text-muted-foreground shrink-0">{p.count}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Top Regions">
          {top_regions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <ul className="space-y-1.5 text-sm">
              {top_regions.slice(0, 10).map((r, i) => (
                <li key={i} className="flex justify-between">
                  <span className="truncate mr-2">{r.region}</span>
                  <span className="text-muted-foreground shrink-0">{r.count}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      {/* Recent visits */}
      <Section title="Recent Visits">
        {recent_visits.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-2 pr-4">Time</th>
                  <th className="pb-2 pr-4">IP</th>
                  <th className="pb-2 pr-4">Region</th>
                  <th className="pb-2 pr-4">Path</th>
                  <th className="pb-2">User Agent</th>
                </tr>
              </thead>
              <tbody>
                {recent_visits.map((v, i) => (
                  <tr key={i} className="border-b border-border/50">
                    <td className="py-1.5 pr-4 font-mono whitespace-nowrap">{v.timestamp ? new Date(v.timestamp).toLocaleString() : '-'}</td>
                    <td className="py-1.5 pr-4 font-mono">{v.ip}</td>
                    <td className="py-1.5 pr-4">{v.region || '-'}</td>
                    <td className="py-1.5 pr-4 truncate max-w-[200px]">{v.path}</td>
                    <td className="py-1.5 truncate max-w-[200px]">{v.user_agent || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Crawl Tab
// ---------------------------------------------------------------------------
function CrawlTab({ data, onRefresh, onStart, starting, targets, addTarget, deleteTarget, importDefaults }) {
  const [newId, setNewId] = useState('')
  const [newName, setNewName] = useState('')

  const handleAddTarget = async (e) => {
    e.preventDefault()
    if (!newId.trim() || !newName.trim()) return
    addTarget.mutate(
      { institutionId: newId.trim(), institutionName: newName.trim() },
      { onSuccess: (res) => { if (res.ok) { setNewId(''); setNewName('') } } }
    )
  }

  const handleDeleteTarget = (institutionId) => {
    deleteTarget.mutate(institutionId)
  }

  const handleImportDefaults = () => {
    importDefaults.mutate()
  }

  if (!data) return <p className="text-muted-foreground py-8 text-center">Loading crawl status...</p>

  return (
    <div className="space-y-6">
      <div className="flex gap-3">
        <button
          onClick={onStart}
          disabled={starting}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50 transition text-sm"
        >
          <Play className="w-4 h-4" />
          {starting ? 'Starting...' : 'Start Crawl'}
        </button>
        <button
          onClick={onRefresh}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-card hover:bg-muted transition text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Crawl Targets Section */}
      <Section title="Crawl Targets">
        <div className="space-y-4">
          <div className="flex gap-3 flex-wrap">
            <form onSubmit={handleAddTarget} className="flex gap-2 items-center flex-wrap">
              <input
                type="text"
                placeholder="Institution ID (e.g. I99065089)"
                value={newId}
                onChange={(e) => setNewId(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-border bg-background text-sm w-52"
              />
              <input
                type="text"
                placeholder="Institution Name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-border bg-background text-sm w-48"
              />
              <button
                type="submit"
                disabled={addTarget.isPending || !newId.trim() || !newName.trim()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50 transition text-sm"
              >
                <Plus className="w-3.5 h-3.5" />
                Add
              </button>
            </form>
            <button
              onClick={handleImportDefaults}
              disabled={importDefaults.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted transition text-sm"
            >
              <Download className="w-3.5 h-3.5" />
              {importDefaults.isPending ? 'Importing...' : 'Import Defaults'}
            </button>
          </div>

          {targets && targets.targets?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="pb-2 pr-4">Institution ID</th>
                    <th className="pb-2 pr-4">Name</th>
                    <th className="pb-2 pr-4">Added</th>
                    <th className="pb-2 w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {targets.targets.map((t) => (
                    <tr key={t.institution_id} className="border-b border-border/50">
                      <td className="py-1.5 pr-4 font-mono">{t.institution_id}</td>
                      <td className="py-1.5 pr-4">{t.institution_name}</td>
                      <td className="py-1.5 pr-4 font-mono text-muted-foreground whitespace-nowrap">{t.created_at ? new Date(t.created_at).toLocaleDateString() : '-'}</td>
                      <td className="py-1.5">
                        <button
                          onClick={() => handleDeleteTarget(t.institution_id)}
                          className="p-1 rounded hover:bg-red-500/10 text-red-500 transition"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No crawl targets configured. Import defaults or add manually.</p>
          )}
        </div>
      </Section>

      {/* Crawl Status Section */}
      <Section title="Crawl Status">
        {data.institutions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No institution crawl records yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-2 pr-4">Institution</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">Works Crawled</th>
                  <th className="pb-2 pr-4">Last Completed</th>
                  <th className="pb-2">Error</th>
                </tr>
              </thead>
              <tbody>
                {data.institutions.map((inst) => (
                  <tr key={inst.institution_id} className="border-b border-border/50">
                    <td className="py-2 pr-4 font-medium">{inst.institution_name || inst.institution_id}</td>
                    <td className="py-2 pr-4"><StatusBadge status={inst.status} /></td>
                    <td className="py-2 pr-4">{inst.total_works_crawled?.toLocaleString()}</td>
                    <td className="py-2 pr-4 font-mono whitespace-nowrap">{inst.last_crawl_completed ? new Date(inst.last_crawl_completed).toLocaleString() : '-'}</td>
                    <td className="py-2 truncate max-w-[300px] text-red-500">{inst.error_message || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------
function Section({ title, children }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <h3 className="text-sm font-semibold text-foreground mb-4">{title}</h3>
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function AdminDashboardPage() {
  const { isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState('analytics')

  const isAnalyticsTab = tab === 'analytics'
  const isCrawlTab = tab === 'crawl'

  const { data: analytics } = useAdminAnalytics(30, { enabled: isAuthenticated && isAnalyticsTab })
  const { data: crawlData } = useAdminCrawlStatus({ enabled: isAuthenticated && isCrawlTab })
  const { data: targets } = useAdminCrawlTargets({ enabled: isAuthenticated && isCrawlTab })

  const startCrawl = useStartCrawl()
  const addTarget = useAddCrawlTarget()
  const deleteTarget = useDeleteCrawlTarget()
  const importDefaults = useInitCrawlTargets()

  const handleStart = () => {
    startCrawl.mutate()
  }

  const handleRefreshCrawl = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlStatus })
  }

  const handleLogout = () => { logout(); navigate('/admin/login') }

  if (!isAuthenticated) {
    navigate('/admin/login', { replace: true })
    return null
  }

  const tabs = [
    { id: 'analytics', label: 'Visitor Analytics', icon: BarChart3 },
    { id: 'crawl', label: 'Crawl Management', icon: Bot },
  ]

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6 pb-12">
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
      <div className="flex gap-2 border-b border-border pb-0">
        {tabs.map((t) => {
          const Icon = t.icon
          const active = tab === t.id
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition -mb-px ${
                active
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      {tab === 'analytics' ? (
        <AnalyticsTab data={analytics} />
      ) : (
        <CrawlTab
          data={crawlData}
          onRefresh={handleRefreshCrawl}
          onStart={handleStart}
          starting={startCrawl.isPending}
          targets={targets}
          addTarget={addTarget}
          deleteTarget={deleteTarget}
          importDefaults={importDefaults}
        />
      )}
    </motion.div>
  )
}
