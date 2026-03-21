import { useState, useRef, useEffect, useCallback } from 'react'
import { Plus, Trash2, Download, Search, Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import Section from './Section'
import CrawlStatusCards from './CrawlStatusCards'
import CrawlBatchControls from './CrawlBatchControls'
import CrawlQueueTable from './CrawlQueueTable'
import CrawlDetailSheet from './CrawlDetailSheet'
import { useAuth } from '@/contexts/AuthContext'
import api from '@/api/client'
import {
  useAdminCrawlStatus,
  useAdminCrawlTargets,
  useAddCrawlTarget,
  useDeleteCrawlTarget,
  useInitCrawlTargets,
  useCrawlProgress,
} from '@/hooks/queries'

export default function CrawlTab() {
  const { role } = useAuth()
  const isAdmin = role === 'admin'
  const [searchQuery, setSearchQuery] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [searching, setSearching] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [selectedInst, setSelectedInst] = useState(null)
  const searchRef = useRef(null)
  const debounceRef = useRef(null)

  const { data: crawlData, isLoading: statusLoading } = useAdminCrawlStatus()
  const { data: targets, isLoading: targetsLoading } = useAdminCrawlTargets()
  const { data: progress } = useCrawlProgress()
  const addTarget = useAddCrawlTarget()
  const deleteTarget = useDeleteCrawlTarget()
  const importDefaults = useInitCrawlTargets()

  // Prefer progress data (richer), fall back to crawlData
  const displayData = progress || crawlData

  // Debounced search for OpenAlex institutions
  const handleSearch = useCallback((query) => {
    setSearchQuery(query)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!query || query.trim().length < 2) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }
    debounceRef.current = setTimeout(async () => {
      setSearching(true)
      try {
        const data = await api.searchOpenAlexInstitution(query.trim())
        setSuggestions(data.results || [])
        setShowSuggestions(true)
      } catch (e) {
        setSuggestions([])
      } finally {
        setSearching(false)
      }
    }, 300)
  }, [])

  const handleSelectSuggestion = (item) => {
    addTarget.mutate(
      { institutionId: item.institution_id, institutionName: item.display_name },
      { onSuccess: () => { setSearchQuery(''); setSuggestions([]); setShowSuggestions(false) } }
    )
  }

  // Close suggestions on click outside
  useEffect(() => {
    const handler = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleDeleteTarget = (institutionId) => {
    if (!confirm('Are you sure you want to delete this crawl target?')) return
    deleteTarget.mutate(institutionId)
  }

  if (statusLoading || targetsLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-10 w-64 rounded-lg" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <CrawlStatusCards data={displayData} />

      {/* Batch controls */}
      {isAdmin ? (
        <CrawlBatchControls data={displayData} />
      ) : (
        <div className="flex items-center">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted text-muted-foreground text-xs font-medium">
            查看模式
          </span>
        </div>
      )}

      {/* Target management */}
      <Section title="Crawl Targets">
        <div className="space-y-4">
          {isAdmin && (
            <div className="flex gap-3 items-start flex-wrap">
              {/* Institution search with autocomplete */}
              <div ref={searchRef} className="relative">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                  {searching && (
                    <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground animate-spin" />
                  )}
                  <input
                    type="text"
                    placeholder="Search institution name to add..."
                    value={searchQuery}
                    onChange={(e) => handleSearch(e.target.value)}
                    onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                    className="pl-8 pr-8 py-1.5 rounded-lg border border-border bg-background text-sm w-80 focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
                {showSuggestions && suggestions.length > 0 && (
                  <div className="absolute z-50 top-full mt-1 w-full bg-card border border-border rounded-lg shadow-lg overflow-hidden">
                    {suggestions.map((item) => (
                      <button
                        key={item.institution_id}
                        onClick={() => handleSelectSuggestion(item)}
                        disabled={addTarget.isPending}
                        className="w-full text-left px-3 py-2 hover:bg-muted transition text-sm border-b border-border/50 last:border-0"
                      >
                        <div className="font-medium text-foreground">{item.display_name}</div>
                        <div className="flex gap-3 text-xs text-muted-foreground mt-0.5">
                          <span className="font-mono">{item.institution_id}</span>
                          {item.country_code && <span>{item.country_code}</span>}
                          {item.works_count > 0 && <span>{item.works_count.toLocaleString()} works</span>}
                          {item.type && <span>{item.type}</span>}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <button
                onClick={() => importDefaults.mutate()}
                disabled={importDefaults.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted transition text-sm"
              >
                <Download className="w-3.5 h-3.5" />
                {importDefaults.isPending ? 'Importing...' : 'Import Defaults'}
              </button>
            </div>
          )}

          {targets && targets.targets?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="pb-2 pr-4">Institution ID</th>
                    <th className="pb-2 pr-4">Name</th>
                    <th className="pb-2 pr-4">Added</th>
                    {isAdmin && <th className="pb-2 w-10"></th>}
                  </tr>
                </thead>
                <tbody>
                  {targets.targets.map((t) => (
                    <tr key={t.institution_id} className="border-b border-border/50">
                      <td className="py-1.5 pr-4 font-mono">{t.institution_id}</td>
                      <td className="py-1.5 pr-4">{t.institution_name}</td>
                      <td className="py-1.5 pr-4 font-mono text-muted-foreground whitespace-nowrap">{t.created_at ? new Date(t.created_at).toLocaleDateString() : '-'}</td>
                      {isAdmin && (
                        <td className="py-1.5">
                          <button
                            onClick={() => handleDeleteTarget(t.institution_id)}
                            className="p-1 rounded hover:bg-red-500/10 text-red-500 transition"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      )}
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

      {/* Queue table */}
      <Section title="Crawl Queue">
        <CrawlQueueTable data={displayData} onDetail={(inst) => setSelectedInst(inst)} role={role} />
      </Section>

      {/* Detail sheet */}
      <CrawlDetailSheet
        institution={selectedInst}
        open={!!selectedInst}
        onClose={() => setSelectedInst(null)}
      />
    </div>
  )
}
