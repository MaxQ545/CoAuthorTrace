import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useInstitutions, useInstitutionRanking } from '../hooks/queries';
import ResearchFieldsBadges from '../components/ResearchFieldsBadges';
import { Building2, ChevronRight, GraduationCap, FileText, Quote, Loader2, AlertCircle, ExternalLink } from 'lucide-react';
import { cn } from '../lib/utils';
import { motion } from 'framer-motion';

const DEBOUNCE_DELAY_MS = 300;

function RankingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [institutionQuery, setInstitutionQuery] = useState('');

  useEffect(() => {
    document.title = '机构排行 - CoAuthorTrace';
    return () => { document.title = '论文合作者追踪系统'; };
  }, []);
  const [debouncedQuery, setDebouncedQuery] = useState('');

  const selectedInstitutionId = searchParams.get('institution_id');

  // Debounce the institution query
  useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedQuery(institutionQuery);
    }, DEBOUNCE_DELAY_MS);
    return () => clearTimeout(handle);
  }, [institutionQuery]);

  const { data: institutions = [], isLoading: institutionsLoading, isFetched: institutionsFetched } = useInstitutions(debouncedQuery);
  const { data: ranking, isLoading: rankingLoading, error: rankingError } = useInstitutionRanking(selectedInstitutionId);

  // Auto-select first institution if none selected and list available
  useEffect(() => {
    if (!selectedInstitutionId && institutions.length > 0) {
      setSearchParams({ institution_id: institutions[0].id });
    }
  }, [institutions, selectedInstitutionId, setSearchParams]);

  const initialLoading = !institutionsFetched && institutionsLoading;

  const handleInstitutionSelect = (institutionId) => {
    setSearchParams({ institution_id: institutionId });
  };

  if (initialLoading && !institutions.length) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
        <Loader2 className="h-10 w-10 animate-spin mb-4 text-primary" />
        <p>正在加载机构数据...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground mb-2">机构学者排行</h1>
        <p className="text-muted-foreground">
          查看各合作机构的学者影响力排名，基于发表论文数量与引用影响力。
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Institution List - Sidebar */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-card rounded-xl border border-border shadow-sm p-4 sticky top-24">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4 px-2">
              合作机构 ({institutions.length})
            </h2>
            <div className="px-2 mb-3">
              <input
                type="text"
                value={institutionQuery}
                onChange={(e) => setInstitutionQuery(e.target.value)}
                placeholder="搜索机构..."
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
              {institutionsLoading && (
                <div className="text-xs text-muted-foreground mt-2">正在更新机构列表...</div>
              )}
            </div>
            <div className="space-y-1 max-h-[calc(100vh-12rem)] overflow-y-auto pr-1 scrollbar-thin">
              {institutions.map((inst) => (
                <button
                  key={inst.id}
                  onClick={() => handleInstitutionSelect(inst.id)}
                  className={cn(
                    "w-full text-left px-3 py-2.5 rounded-lg transition-all duration-200 flex flex-col group",
                    selectedInstitutionId === inst.id
                      ? "bg-primary text-primary-foreground shadow-md"
                      : "hover:bg-secondary text-foreground"
                  )}
                >
                  <div className="font-medium text-sm truncate w-full flex items-center justify-between">
                    <span className="truncate">{inst.name}</span>
                    {selectedInstitutionId === inst.id && <ChevronRight size={14} />}
                  </div>
                  <div className={cn(
                    "text-xs mt-0.5",
                    selectedInstitutionId === inst.id ? "text-primary-foreground/80" : "text-muted-foreground"
                  )}>
                    {inst.author_count} 位学者
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Ranking Table - Main Content */}
        <div className="lg:col-span-9">
          {selectedInstitutionId ? (
            rankingLoading ? (
              <div className="flex flex-col items-center justify-center h-64 text-muted-foreground bg-card rounded-xl border border-border">
                <Loader2 className="h-8 w-8 animate-spin mb-3 text-primary" />
                <p>正在计算排名数据...</p>
              </div>
            ) : rankingError ? (
              <div className="bg-destructive/10 border border-destructive/20 rounded-xl p-8 text-center text-destructive">
                <AlertCircle className="h-10 w-10 mx-auto mb-4" />
                <p className="font-medium">加载排名数据失败，请稍后重试</p>
              </div>
            ) : ranking ? (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-card rounded-xl border border-border shadow-sm overflow-hidden"
              >
                <div className="px-6 py-5 border-b border-border bg-muted/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary/10 rounded-lg text-primary">
                      <Building2 size={24} />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-foreground">
                        {ranking.institution_name}
                      </h2>
                      <p className="text-sm text-muted-foreground">
                        共收录 {ranking.total} 位学者
                      </p>
                    </div>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-muted/50 text-muted-foreground font-medium border-b border-border">
                      <tr>
                        <th className="py-4 px-6 w-16 text-center">排名</th>
                        <th className="py-4 px-6">学者</th>
                        <th className="py-4 px-6 hidden md:table-cell">研究领域</th>
                        <th className="py-4 px-6 text-right w-24">论文数</th>
                        <th className="py-4 px-6 text-right w-24">被引数</th>
                        <th className="py-4 px-6 text-center w-20">ORCID</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {ranking.authors.map((author) => (
                        <tr
                          key={author.id}
                          className="hover:bg-muted/30 transition-colors group"
                        >
                          <td className="py-3 px-6 text-center">
                            <span className={cn(
                              "inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold",
                              author.rank <= 3
                                ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400"
                                : author.rank <= 10
                                ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400"
                                : "text-muted-foreground bg-secondary"
                            )}>
                              {author.rank}
                            </span>
                          </td>
                          <td className="py-3 px-6">
                            <Link
                              to={`/author/${author.id}`}
                              className="font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-2"
                            >
                              {author.display_name}
                            </Link>
                          </td>
                          <td className="py-3 px-6 hidden md:table-cell">
                            <ResearchFieldsBadges fields={author.research_fields} maxDisplay={2} />
                          </td>
                          <td className="py-3 px-6 text-right font-mono text-muted-foreground">
                            {author.works_count}
                          </td>
                          <td className="py-3 px-6 text-right font-mono text-muted-foreground">
                            {author.cited_by_count}
                          </td>
                          <td className="py-3 px-6 text-center">
                            {author.orcid ? (
                              <a
                                href={author.orcid}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center justify-center text-emerald-600 hover:text-emerald-500 transition-colors"
                                title={author.orcid}
                              >
                                <ExternalLink size={14} />
                              </a>
                            ) : (
                              <span className="text-muted-foreground/30">-</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            ) : null
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground bg-card rounded-xl border border-dashed border-border">
              <Building2 className="h-12 w-12 opacity-20 mb-4" />
              <p>请从左侧选择一个机构查看排名</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default RankingPage;
