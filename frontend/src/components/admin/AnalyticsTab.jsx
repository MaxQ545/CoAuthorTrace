import { useState } from 'react'
import { Eye, Users, Calendar, TrendingUp, ChevronLeft, ChevronRight } from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import StatsCard from '@/components/StatsCard'
import Section from './Section'
import VisitChart from './VisitChart'
import { useAdminAnalytics, useAdminVisits } from '@/hooks/queries'

function HBarTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-md text-sm">
      <p className="font-medium text-foreground">{payload[0].payload.label}</p>
      <p className="text-muted-foreground">{payload[0].value.toLocaleString()} visits</p>
    </div>
  )
}

const PAGE_SIZE = 20

export default function AnalyticsTab() {
  const [visitsPage, setVisitsPage] = useState(0)
  const { data, isLoading } = useAdminAnalytics(30)
  const { data: visitsData, isFetching: visitsFetching } = useAdminVisits(PAGE_SIZE, visitsPage * PAGE_SIZE)

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-72 rounded-xl" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      </div>
    )
  }

  if (!data) return <p className="text-muted-foreground py-8 text-center">No analytics data.</p>

  const { summary, daily_visits, top_pages, top_regions } = data

  const pagesData = top_pages.slice(0, 10).map((p) => ({
    label: p.author_name ? `${p.path} (${p.author_name})` : p.path,
    count: p.count,
  }))

  const regionsData = top_regions.slice(0, 10).map((r) => ({
    label: r.region,
    count: r.count,
  }))

  return (
    <div className="space-y-8">
      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard icon={<Eye size={24} />} title="Total Visits" value={summary.total?.toLocaleString() ?? '-'} color="blue" delay={0} />
        <StatsCard icon={<Users size={24} />} title="Unique Visitors" value={summary.unique_ips?.toLocaleString() ?? '-'} color="green" delay={0.05} />
        <StatsCard icon={<Calendar size={24} />} title="Today" value={summary.today?.toLocaleString() ?? '-'} color="purple" delay={0.1} />
        <StatsCard icon={<TrendingUp size={24} />} title="This Week" value={summary.this_week?.toLocaleString() ?? '-'} color="orange" delay={0.15} />
      </div>

      {/* Daily visits area chart */}
      <Section title="Daily Visits (Last 30 Days)">
        <VisitChart data={daily_visits} />
      </Section>

      {/* Top pages & regions as horizontal bar charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Section title="Top Pages">
          {pagesData.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(pagesData.length * 32, 100)}>
              <BarChart data={pagesData} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} className="text-muted-foreground" tickLine={false} axisLine={false} allowDecimals={false} />
                <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} className="text-muted-foreground" width={140} tickLine={false} axisLine={false} />
                <Tooltip content={<HBarTooltip />} />
                <Bar dataKey="count" fill="hsl(221, 83%, 53%)" radius={[0, 4, 4, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Section>

        <Section title="Top Regions">
          {regionsData.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(regionsData.length * 32, 100)}>
              <BarChart data={regionsData} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} className="text-muted-foreground" tickLine={false} axisLine={false} allowDecimals={false} />
                <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} className="text-muted-foreground" width={120} tickLine={false} axisLine={false} />
                <Tooltip content={<HBarTooltip />} />
                <Bar dataKey="count" fill="hsl(160, 60%, 45%)" radius={[0, 4, 4, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Section>
      </div>

      {/* Recent visits table with pagination */}
      <Section title="Recent Visits">
        {!visitsData || visitsData.visits?.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data yet.</p>
        ) : (
          <div className="space-y-3">
            <div className={`overflow-x-auto ${visitsFetching ? 'opacity-60' : ''} transition-opacity`}>
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
                  {visitsData.visits.map((v, i) => (
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
            {/* Pagination controls */}
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                {visitsData.offset + 1}-{Math.min(visitsData.offset + visitsData.visits.length, visitsData.total)} of {visitsData.total.toLocaleString()}
              </span>
              <div className="flex gap-1">
                <button
                  onClick={() => setVisitsPage(p => p - 1)}
                  disabled={visitsPage === 0}
                  className="p-1.5 rounded-md border border-border hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed transition"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setVisitsPage(p => p + 1)}
                  disabled={visitsData.offset + visitsData.visits.length >= visitsData.total}
                  className="p-1.5 rounded-md border border-border hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed transition"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </Section>
    </div>
  )
}
