import { useState } from 'react'
import { Play, Pause, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { useStartCrawl, useStopCrawl } from '@/hooks/queries'

export default function CrawlBatchControls({ data }) {
  const [confirmStopAll, setConfirmStopAll] = useState(false)
  const startCrawl = useStartCrawl()
  const stopCrawl = useStopCrawl()

  const institutions = data?.institutions || []
  const hasRunning = institutions.some(i => ['running', 'pause_requested'].includes(i.status))
  const hasQueued = institutions.some(i => i.status === 'queued')
  const runningList = institutions.filter(i => ['running', 'pause_requested', 'stop_requested'].includes(i.status))

  const handleStopAll = () => {
    stopCrawl.mutate()
    setConfirmStopAll(false)
  }

  return (
    <>
      <div className="flex items-center gap-2 flex-wrap">
        <Button
          size="sm"
          onClick={() => startCrawl.mutate()}
          disabled={startCrawl.isPending || hasRunning}
        >
          <Play className="w-4 h-4" />
          {startCrawl.isPending ? 'Starting...' : 'Start Queue'}
        </Button>

        <Button
          size="sm"
          variant="destructive"
          onClick={() => setConfirmStopAll(true)}
          disabled={!hasRunning || stopCrawl.isPending}
        >
          <Square className="w-4 h-4" />
          Stop All
        </Button>

        {data && (
          <span className="text-xs text-muted-foreground ml-auto">
            {institutions.length} institution{institutions.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      <Dialog open={confirmStopAll} onOpenChange={setConfirmStopAll}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Stop All Crawls?</DialogTitle>
            <DialogDescription>
              This will send a stop signal to {runningList.length} active crawl{runningList.length !== 1 ? 's' : ''}.
            </DialogDescription>
          </DialogHeader>
          {runningList.length > 0 && (
            <ul className="text-sm space-y-1 max-h-40 overflow-y-auto">
              {runningList.map((inst) => (
                <li key={inst.institution_id} className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                  {inst.institution_name || inst.institution_id}
                </li>
              ))}
            </ul>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmStopAll(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleStopAll} disabled={stopCrawl.isPending}>
              {stopCrawl.isPending ? 'Stopping...' : 'Stop All'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
