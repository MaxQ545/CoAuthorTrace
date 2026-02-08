import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

const statusConfig = {
  running: {
    color: 'bg-blue-500/10 text-blue-600 border-blue-500/20 dark:text-blue-400',
    dot: 'bg-blue-500',
    pulse: true,
  },
  completed: {
    color: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400',
    dot: 'bg-emerald-500',
    pulse: false,
  },
  failed: {
    color: 'bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400',
    dot: 'bg-red-500',
    pulse: false,
  },
  queued: {
    color: 'bg-violet-500/10 text-violet-600 border-violet-500/20 dark:text-violet-400',
    dot: 'bg-violet-500',
    pulse: false,
  },
  idle: {
    color: 'bg-muted text-muted-foreground border-border',
    dot: 'bg-muted-foreground/50',
    pulse: false,
  },
  paused: {
    color: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20 dark:text-yellow-400',
    dot: 'bg-yellow-500',
    pulse: false,
  },
  pause_requested: {
    color: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20 dark:text-yellow-400',
    dot: 'bg-yellow-500',
    pulse: true,
  },
  stop_requested: {
    color: 'bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400',
    dot: 'bg-amber-500',
    pulse: true,
  },
  stopped: {
    color: 'bg-muted text-muted-foreground border-border',
    dot: 'bg-muted-foreground/50',
    pulse: false,
  },
}

const labels = {
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  queued: 'Queued',
  idle: 'Idle',
  paused: 'Paused',
  pause_requested: 'Pausing',
  stop_requested: 'Stopping',
  stopped: 'Stopped',
}

export default function StatusBadge({ status, className }) {
  const config = statusConfig[status] || statusConfig.idle

  return (
    <Badge
      variant="outline"
      className={cn(
        'gap-1.5 font-medium',
        config.color,
        className
      )}
    >
      <span
        className={cn(
          'h-1.5 w-1.5 rounded-full',
          config.dot,
          config.pulse && 'animate-pulse'
        )}
      />
      {labels[status] || status}
    </Badge>
  )
}
