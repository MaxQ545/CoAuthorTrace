import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import StatusBadge from './StatusBadge'
import CrawlProgressBar from './CrawlProgressBar'

function DetailRow({ label, value }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-border/50">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value ?? '-'}</span>
    </div>
  )
}

function formatDuration(startStr, endStr) {
  if (!startStr) return '-'
  const start = new Date(startStr)
  const end = endStr ? new Date(endStr) : new Date()
  const diffMs = end - start
  const mins = Math.floor(diffMs / 60000)
  const secs = Math.floor((diffMs % 60000) / 1000)
  if (mins > 60) {
    const hrs = Math.floor(mins / 60)
    return `${hrs}h ${mins % 60}m`
  }
  return `${mins}m ${secs}s`
}

export default function CrawlDetailSheet({ institution, open, onClose }) {
  if (!institution) return null

  const current = institution.progress_current ?? 0
  const total = institution.progress_total ?? 0

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{institution.institution_name || institution.institution_id}</SheetTitle>
          <SheetDescription className="flex items-center gap-2">
            <StatusBadge status={institution.status} />
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Progress */}
          <div>
            <h4 className="text-sm font-medium mb-2">Progress</h4>
            <CrawlProgressBar
              current={current}
              total={total}
              status={institution.status}
            />
          </div>

          {/* Details */}
          <div>
            <h4 className="text-sm font-medium mb-2">Details</h4>
            <div className="space-y-0">
              <DetailRow label="Institution ID" value={institution.institution_id} />
              <DetailRow label="Status" value={institution.status} />
              <DetailRow label="Works Crawled" value={current.toLocaleString()} />
              {total > 0 && <DetailRow label="Total Works" value={total.toLocaleString()} />}
              <DetailRow
                label="Started"
                value={institution.started_at ? new Date(institution.started_at).toLocaleString() : undefined}
              />
              <DetailRow
                label="Elapsed"
                value={institution.started_at ? formatDuration(institution.started_at, institution.last_crawl_completed) : undefined}
              />
              <DetailRow
                label="Last Completed"
                value={institution.last_crawl_completed ? new Date(institution.last_crawl_completed).toLocaleString() : undefined}
              />
              {current > 0 && institution.started_at && (
                <DetailRow
                  label="Rate"
                  value={(() => {
                    const start = new Date(institution.started_at)
                    const end = institution.last_crawl_completed ? new Date(institution.last_crawl_completed) : new Date()
                    const mins = (end - start) / 60000
                    if (mins <= 0) return '-'
                    return `${Math.round(current / mins)} works/min`
                  })()}
                />
              )}
            </div>
          </div>

          {/* Error */}
          {institution.error_message && (
            <div>
              <h4 className="text-sm font-medium mb-2 text-red-500">Error</h4>
              <p className="text-sm text-red-500/80 bg-red-500/5 rounded-lg p-3 font-mono text-xs break-all">
                {institution.error_message}
              </p>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
