import { cn } from '@/lib/utils'

const colorMap = {
  running: 'bg-blue-500',
  completed: 'bg-emerald-500',
  failed: 'bg-red-500',
  paused: 'bg-yellow-500',
  pause_requested: 'bg-yellow-500',
  stop_requested: 'bg-amber-500',
  queued: 'bg-violet-500',
}

export default function CrawlProgressBar({ current = 0, total = 0, status = 'idle' }) {
  const pct = total > 0 ? Math.min(Math.round((current / total) * 100), 100) : 0
  const barColor = colorMap[status] || 'bg-muted-foreground/30'

  return (
    <div className="flex items-center gap-3 min-w-[180px]">
      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-primary/10">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            barColor,
            status === 'running' && 'animate-pulse'
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground tabular-nums whitespace-nowrap">
        {total > 0 ? `${current.toLocaleString()} / ${total.toLocaleString()}` : '--'}
      </span>
    </div>
  )
}
