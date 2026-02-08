import { useState, useMemo, useCallback, useEffect } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  flexRender,
} from '@tanstack/react-table'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { restrictToVerticalAxis } from '@dnd-kit/modifiers'
import { GripVertical, Pause, Play, Square, RotateCcw, Eye, Search, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import StatusBadge from './StatusBadge'
import CrawlProgressBar from './CrawlProgressBar'
import {
  useStopInstitution,
  usePauseCrawl,
  useResumeCrawl,
  useRetryCrawl,
  useReorderQueue,
} from '@/hooks/queries'

const statusFilters = [
  { id: 'all', label: 'All' },
  { id: 'active', label: 'Active', match: ['running', 'pause_requested', 'stop_requested'] },
  { id: 'completed', label: 'Completed', match: ['completed'] },
  { id: 'failed', label: 'Failed', match: ['failed', 'stopped'] },
  { id: 'queued', label: 'Queued', match: ['queued'] },
]

function InlineConfirmButton({ children, onConfirm, variant = 'outline', size = 'sm', className, disabled }) {
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    if (!confirming) return
    const timer = setTimeout(() => setConfirming(false), 3000)
    return () => clearTimeout(timer)
  }, [confirming])

  const handleClick = () => {
    if (confirming) {
      onConfirm()
      setConfirming(false)
    } else {
      setConfirming(true)
    }
  }

  return (
    <Button
      variant={confirming ? 'destructive' : variant}
      size={size}
      className={cn('text-xs', className)}
      onClick={handleClick}
      disabled={disabled}
    >
      {confirming ? 'Confirm?' : children}
    </Button>
  )
}

function ActionButtons({ row, onDetail }) {
  const stopInstitution = useStopInstitution()
  const pauseCrawl = usePauseCrawl()
  const resumeCrawl = useResumeCrawl()
  const retryCrawl = useRetryCrawl()
  const id = row.institution_id
  const status = row.status

  switch (status) {
    case 'running':
      return (
        <div className="flex gap-1">
          <Button variant="outline" size="sm" className="text-xs" onClick={() => pauseCrawl.mutate(id)} disabled={pauseCrawl.isPending}>
            <Pause className="w-3 h-3" /> Pause
          </Button>
          <InlineConfirmButton onConfirm={() => stopInstitution.mutate(id)} disabled={stopInstitution.isPending}>
            <Square className="w-3 h-3" /> Stop
          </InlineConfirmButton>
        </div>
      )
    case 'paused':
      return (
        <div className="flex gap-1">
          <Button variant="outline" size="sm" className="text-xs" onClick={() => resumeCrawl.mutate(id)} disabled={resumeCrawl.isPending}>
            <Play className="w-3 h-3" /> Resume
          </Button>
          <InlineConfirmButton onConfirm={() => stopInstitution.mutate(id)} disabled={stopInstitution.isPending}>
            <Square className="w-3 h-3" /> Stop
          </InlineConfirmButton>
        </div>
      )
    case 'failed':
    case 'stopped':
      return (
        <Button variant="outline" size="sm" className="text-xs" onClick={() => retryCrawl.mutate(id)} disabled={retryCrawl.isPending}>
          <RotateCcw className="w-3 h-3" /> Retry
        </Button>
      )
    case 'queued':
      return (
        <Button variant="outline" size="sm" className="text-xs" onClick={() => retryCrawl.mutate(id)} disabled={retryCrawl.isPending}>
          <Play className="w-3 h-3" /> Start
        </Button>
      )
    case 'completed':
      return onDetail ? (
        <Button variant="ghost" size="sm" className="text-xs" onClick={() => onDetail(row)}>
          <Eye className="w-3 h-3" /> View
        </Button>
      ) : null
    default:
      return null
  }
}

function SortableRow({ row, children }) {
  const isQueued = row.original.status === 'queued'
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: row.original.institution_id,
    disabled: !isQueued,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <tr ref={setNodeRef} style={style} className="border-b border-border/50 hover:bg-muted/50">
      {children.map((cell, i) =>
        i === 0 ? (
          <td key={i} className="py-2 px-2 w-8">
            {isQueued ? (
              <span {...attributes} {...listeners} className="cursor-grab text-muted-foreground hover:text-foreground">
                <GripVertical className="w-4 h-4" />
              </span>
            ) : (
              <span className="text-muted-foreground/30">
                <GripVertical className="w-4 h-4" />
              </span>
            )}
          </td>
        ) : (
          <td key={cell?.key || i} className={cn('py-2 px-2', i === 1 && 'font-medium')}>
            {cell}
          </td>
        )
      )}
    </tr>
  )
}

export default function CrawlQueueTable({ data, onDetail }) {
  const [statusFilter, setStatusFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [localOrder, setLocalOrder] = useState(null)
  const reorderQueue = useReorderQueue()

  const institutions = useMemo(() => {
    const list = data?.institutions || []
    if (localOrder && statusFilter === 'all') {
      const orderMap = new Map(localOrder.map((id, idx) => [id, idx]))
      return [...list].sort((a, b) =>
        (orderMap.get(a.institution_id) ?? 999) - (orderMap.get(b.institution_id) ?? 999)
      )
    }
    return list
  }, [data, localOrder, statusFilter])

  const filtered = useMemo(() => {
    let result = institutions
    // Status filter
    if (statusFilter !== 'all') {
      const filter = statusFilters.find(f => f.id === statusFilter)
      if (filter?.match) {
        result = result.filter(i => filter.match.includes(i.status))
      }
    }
    // Search filter (fuzzy match on name or ID)
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase()
      result = result.filter(i =>
        (i.institution_name || '').toLowerCase().includes(q) ||
        (i.institution_id || '').toLowerCase().includes(q)
      )
    }
    return result
  }, [institutions, statusFilter, searchQuery])

  const filterCounts = useMemo(() => {
    const all = data?.institutions || []
    const counts = {}
    for (const f of statusFilters) {
      if (f.id === 'all') { counts.all = all.length; continue }
      counts[f.id] = all.filter(i => f.match.includes(i.status)).length
    }
    return counts
  }, [data])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor)
  )

  const handleDragEnd = useCallback((event) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const currentIds = institutions.map(i => i.institution_id)
    const oldIdx = currentIds.indexOf(active.id)
    const newIdx = currentIds.indexOf(over.id)
    if (oldIdx === -1 || newIdx === -1) return

    const newOrder = arrayMove(currentIds, oldIdx, newIdx)
    setLocalOrder(newOrder)
    reorderQueue.mutate(newOrder, {
      onError: () => setLocalOrder(null),
    })
  }, [institutions, reorderQueue])

  const rowIds = useMemo(() => filtered.map(i => i.institution_id), [filtered])

  return (
    <div className="space-y-3">
      {/* Status filter tabs + search */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex gap-1 flex-wrap">
          {statusFilters.map((f) => (
            <button
              key={f.id}
              onClick={() => setStatusFilter(f.id)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition',
                statusFilter === f.id
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              )}
            >
              {f.label}
              {filterCounts[f.id] > 0 && (
                <Badge variant="secondary" className="ml-1 h-4 px-1 text-[10px] leading-none">
                  {filterCounts[f.id]}
                </Badge>
              )}
            </button>
          ))}
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search institution..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 pr-8 py-1.5 rounded-lg border border-border bg-background text-sm w-56 focus:outline-none focus:ring-1 focus:ring-ring"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">No institutions match this filter.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
            modifiers={[restrictToVerticalAxis]}
          >
            <SortableContext items={rowIds} strategy={verticalListSortingStrategy}>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50 text-left text-muted-foreground">
                    <th className="py-2 px-2 w-8"></th>
                    <th className="py-2 px-2">Institution</th>
                    <th className="py-2 px-2">Status</th>
                    <th className="py-2 px-2">Progress</th>
                    <th className="py-2 px-2">Last Run</th>
                    <th className="py-2 px-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((inst) => (
                    <SortableRow
                      key={inst.institution_id}
                      row={{ original: inst, id: inst.institution_id }}
                    >
                      {[
                        /* drag handle placeholder */ null,
                        <span
                          key="name"
                          className="cursor-pointer hover:underline"
                          onClick={() => onDetail?.(inst)}
                        >
                          {inst.institution_name || inst.institution_id}
                        </span>,
                        <StatusBadge key="status" status={inst.status} />,
                        <CrawlProgressBar
                          key="progress"
                          current={inst.progress_current ?? 0}
                          total={inst.progress_total ?? 0}
                          status={inst.status}
                        />,
                        <span key="time" className="font-mono whitespace-nowrap text-xs text-muted-foreground">
                          {inst.last_crawl_completed
                            ? new Date(inst.last_crawl_completed).toLocaleString()
                            : inst.started_at
                              ? new Date(inst.started_at).toLocaleString()
                              : '-'}
                        </span>,
                        <ActionButtons key="actions" row={inst} onDetail={onDetail} />,
                      ]}
                    </SortableRow>
                  ))}
                </tbody>
              </table>
            </SortableContext>
          </DndContext>
        </div>
      )}
    </div>
  )
}
