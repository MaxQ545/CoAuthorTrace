import { Activity, CheckCircle, XCircle, Clock } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

function KpiCard({ icon: Icon, label, value, color }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
          <Icon className="w-4.5 h-4.5" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-xl font-bold text-foreground tabular-nums">{value}</p>
        </div>
      </CardContent>
    </Card>
  )
}

export default function CrawlStatusCards({ data }) {
  if (!data?.institutions) return null

  const institutions = data.institutions
  const active = institutions.filter(i => ['running', 'pause_requested', 'stop_requested'].includes(i.status)).length
  const completed = institutions.filter(i => i.status === 'completed').length
  const failed = institutions.filter(i => i.status === 'failed').length
  const queued = institutions.filter(i => i.status === 'queued').length
  const total = institutions.length
  const successRate = total > 0 ? Math.round((completed / total) * 100) : 0

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard icon={Activity} label="Active Crawls" value={active} color="bg-blue-500/10 text-blue-600 dark:text-blue-400" />
      <KpiCard icon={CheckCircle} label="Success Rate" value={`${successRate}%`} color="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" />
      <KpiCard icon={XCircle} label="Failed" value={failed} color="bg-red-500/10 text-red-600 dark:text-red-400" />
      <KpiCard icon={Clock} label="Queued" value={queued} color="bg-violet-500/10 text-violet-600 dark:text-violet-400" />
    </div>
  )
}
