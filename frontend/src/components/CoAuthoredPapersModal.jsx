import { useState, useEffect, useMemo } from 'react';
import { useCoAuthoredPapers } from '../hooks/queries';
import { useTimeFilter } from '../contexts/TimeFilterContext';
import { X, Calendar, BookOpen, ExternalLink, ArrowUpDown, Lock, Unlock, Loader2, Quote } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../lib/utils';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

function CoAuthoredPapersModal({
  isOpen,
  onClose,
  authorId,
  authorName,
  collaboratorId,
  collaboratorName
}) {
  const { timeRange } = useTimeFilter();

  // Pagination and sorting state
  const [offset, setOffset] = useState(0);
  const [sortBy, setSortBy] = useState('publication_date');
  const [sortOrder, setSortOrder] = useState('desc');
  const limit = 10; // Smaller limit for modal

  const { data, isLoading: loading, error } = useCoAuthoredPapers(
    authorId,
    collaboratorId,
    limit,
    offset,
    sortBy,
    sortOrder,
    timeRange.fromYear,
    timeRange.toYear
  );

  const papers = data?.papers || [];
  const total = data?.total || 0;

  // Aggregate papers by publication year for mini-timeline chart
  const yearData = useMemo(() => {
    const counts = {};
    for (const paper of papers) {
      const year = paper.publication_year
        || (paper.publication_date ? parseInt(paper.publication_date.slice(0, 4), 10) : null);
      if (year) {
        counts[year] = (counts[year] || 0) + 1;
      }
    }
    return Object.entries(counts)
      .map(([year, count]) => ({ year: Number(year), count }))
      .sort((a, b) => a.year - b.year);
  }, [papers]);

  // Reset when modal opens with new collaborator
  useEffect(() => {
    if (isOpen) {
      setOffset(0);
    }
  }, [isOpen, collaboratorId]);

  const handleSortChange = (newSortBy) => {
    if (newSortBy === sortBy) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(newSortBy);
      setSortOrder('desc');
    }
    setOffset(0);
  };

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="relative w-full max-w-4xl bg-card border border-border rounded-xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="p-6 border-b border-border bg-muted/10 flex items-start justify-between">
              <div>
                <h2 className="text-xl font-bold text-foreground">
                  合作论文详情
                </h2>
                <p className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
                  <span className="font-medium text-foreground">{authorName}</span>
                  <span className="text-muted-foreground/50">×</span>
                  <span className="font-medium text-foreground">{collaboratorName}</span>
                </p>
              </div>
              <button
                onClick={onClose}
                className="p-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-full transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {/* Toolbar */}
            <div className="px-6 py-3 border-b border-border bg-muted/5 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">排序:</span>
                {[
                  { id: 'publication_date', label: '日期' },
                  { id: 'cited_by_count', label: '引用' },
                  { id: 'title', label: '标题' }
                ].map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleSortChange(item.id)}
                    className={cn(
                      "px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1",
                      sortBy === item.id
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "bg-secondary text-muted-foreground hover:bg-secondary/80"
                    )}
                  >
                    {item.label}
                    {sortBy === item.id && <ArrowUpDown size={10} />}
                  </button>
                ))}
              </div>
              <div className="text-xs font-medium text-muted-foreground bg-secondary px-2.5 py-1 rounded-full">
                共 {total} 篇合作论文
              </div>
            </div>

            {/* Mini-timeline chart */}
            {!loading && papers.length >= 2 && yearData.length > 0 && (
              <div className="px-6 pt-4 pb-2 border-b border-border">
                <ResponsiveContainer width="100%" height={100}>
                  <BarChart data={yearData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                    <XAxis
                      dataKey="year"
                      tick={{ fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      width={30}
                    />
                    <Tooltip
                      contentStyle={{ fontSize: 12, borderRadius: 8 }}
                      formatter={(value) => [`${value} 篇`, '论文数']}
                      labelFormatter={(label) => `${label} 年`}
                    />
                    <Bar dataKey="count" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* List Content */}
            <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
              {loading ? (
                <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                  <Loader2 className="h-8 w-8 animate-spin mb-3 text-primary" />
                  <p>正在加载...</p>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center h-48 text-destructive">
                  <p className="font-medium mb-2">无法加载论文列表</p>
                </div>
              ) : papers.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  暂无符合条件的论文数据
                </div>
              ) : (
                <div className="space-y-4">
                  {papers.map((paper, index) => (
                    <div
                      key={paper.id}
                      className="group p-4 rounded-xl border border-border bg-card hover:border-primary/30 hover:shadow-md transition-all duration-200"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start gap-3">
                            <span className="text-xs font-mono text-muted-foreground mt-1 min-w-[1.5rem]">
                              {offset + index + 1}.
                            </span>
                            <div>
                              <h3 className="text-base font-semibold text-foreground leading-tight mb-2 group-hover:text-primary transition-colors">
                                {paper.title}
                              </h3>

                              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
                                {paper.publication_date && (
                                  <div className="flex items-center gap-1.5 bg-secondary/30 px-2 py-1 rounded">
                                    <Calendar size={12} />
                                    <span>{paper.publication_date}</span>
                                  </div>
                                )}
                                {paper.source_name && (
                                  <div className="flex items-center gap-1.5 max-w-[200px]">
                                    <BookOpen size={12} />
                                    <span className="truncate" title={paper.source_name}>
                                      {paper.source_name}
                                    </span>
                                  </div>
                                )}
                                <div className="flex items-center gap-1.5 text-foreground/80">
                                  <Quote size={12} />
                                  <span className="font-mono font-medium">{paper.cited_by_count}</span>
                                </div>
                                {paper.is_open_access && (
                                  <div className="flex items-center gap-1 text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full dark:bg-emerald-900/20 dark:text-emerald-400">
                                    <Unlock size={10} /> <span>OA</span>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>

                        {paper.doi && (
                          <a
                            href={`https://doi.org/${paper.doi}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="shrink-0 p-2 text-muted-foreground hover:text-primary hover:bg-secondary rounded-lg transition-colors"
                            title="View DOI"
                          >
                            <ExternalLink size={18} />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Pagination Footer */}
            {totalPages > 1 && (
              <div className="p-4 border-t border-border bg-muted/5 flex items-center justify-between">
                <button
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={offset === 0}
                  className="px-4 py-2 text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-secondary transition-colors"
                >
                  上一页
                </button>
                <span className="text-sm font-medium text-muted-foreground">
                  第 <span className="text-foreground">{currentPage}</span> / {totalPages} 页
                </span>
                <button
                  onClick={() => setOffset(offset + limit)}
                  disabled={currentPage >= totalPages}
                  className="px-4 py-2 text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-secondary transition-colors"
                >
                  下一页
                </button>
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

export default CoAuthoredPapersModal;
