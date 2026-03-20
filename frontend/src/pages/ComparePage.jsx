import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuthor, usePublicationTimeline } from '../hooks/queries';
import api from '../api/client';
import {
  Building2,
  BookOpen,
  Quote,
  Loader2,
  AlertTriangle,
  ChevronRight,
  ArrowRightLeft,
  Search,
  X,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';

/* ------------------------------------------------------------------ */
/*  AuthorSearchInput — inline autocomplete for a single compare slot */
/* ------------------------------------------------------------------ */

function AuthorSearchInput({ slot, selectedAuthor, onSelect, onClear, otherAuthorId }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  const containerRef = useRef(null);
  const inputRef = useRef(null);

  const color = slot === 'a' ? 'blue' : 'orange';
  const label = slot === 'a' ? '作者 A' : '作者 B';
  const dotBg = color === 'blue' ? 'bg-blue-500' : 'bg-orange-500';
  const chipBorder = color === 'blue' ? 'border-blue-500/30' : 'border-orange-500/30';
  const chipBg = color === 'blue' ? 'bg-blue-500/10' : 'bg-orange-500/10';
  const chipText = color === 'blue' ? 'text-blue-700 dark:text-blue-300' : 'text-orange-700 dark:text-orange-300';

  // Debounced search
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 1) {
      setSuggestions([]);
      setShowDropdown(false);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    const timeout = setTimeout(async () => {
      try {
        const response = await api.searchAuthors(trimmed, 8, 0, false, true);
        const results = (response.results || []).filter(
          (a) => a.id !== otherAuthorId
        );
        setSuggestions(results);
        setShowDropdown(true);
        setSelectedIndex(-1);
      } catch (error) {
        console.error('Author search failed:', error);
        setSuggestions([]);
        setShowDropdown(false);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [query, otherAuthorId]);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setShowDropdown(false);
        setSelectedIndex(-1);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (author) => {
    onSelect({
      id: author.id,
      display_name: author.display_name,
      institution:
        author.primary_institution_name ||
        author.last_known_institution_name ||
        null,
    });
    setQuery('');
    setSuggestions([]);
    setShowDropdown(false);
    setSelectedIndex(-1);
  };

  const handleKeyDown = (e) => {
    if (!showDropdown || suggestions.length === 0) return;
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && suggestions[selectedIndex]) {
          handleSelect(suggestions[selectedIndex]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setShowDropdown(false);
        setSelectedIndex(-1);
        break;
    }
  };

  const getInstitution = (author) =>
    author.primary_institution_name ||
    author.last_known_institution_name ||
    '未知机构';

  return (
    <div ref={containerRef} className="relative flex-1 min-w-0">
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-2.5 h-2.5 rounded-full ${dotBg}`} />
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {label}
        </span>
      </div>

      {selectedAuthor ? (
        /* Selected author chip */
        <div
          className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${chipBorder} ${chipBg}`}
        >
          <div className="flex-1 min-w-0">
            <Link
              to={`/author/${selectedAuthor.id}`}
              className={`font-semibold ${chipText} hover:underline block truncate`}
            >
              {selectedAuthor.display_name}
            </Link>
            {selectedAuthor.institution && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                <Building2 size={11} />
                <span className="truncate">{selectedAuthor.institution}</span>
              </div>
            )}
          </div>
          <button
            onClick={onClear}
            className="p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors shrink-0"
            title="移除"
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        /* Search input */
        <div className="flex items-center gap-2 px-3 py-2.5 bg-background border border-border rounded-xl focus-within:ring-2 focus-within:ring-primary focus-within:border-primary transition-colors">
          <Search size={15} className="text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="搜索作者姓名..."
            className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground outline-none text-sm"
          />
          {isSearching && (
            <Loader2 size={14} className="animate-spin text-muted-foreground" />
          )}
        </div>
      )}

      {/* Suggestions dropdown */}
      <AnimatePresence>
        {showDropdown && !selectedAuthor && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            transition={{ duration: 0.12 }}
            className="absolute top-full left-0 right-0 mt-1.5 z-50 bg-popover border border-border rounded-xl shadow-xl max-h-72 overflow-y-auto"
          >
            {suggestions.length > 0 ? (
              <ul>
                {suggestions.map((author, index) => (
                  <li
                    key={author.id}
                    className={`px-4 py-3 cursor-pointer transition-colors border-b border-border/50 last:border-b-0 ${
                      index === selectedIndex
                        ? 'bg-accent'
                        : 'hover:bg-accent/50'
                    }`}
                    onClick={() => handleSelect(author)}
                    onMouseEnter={() => setSelectedIndex(index)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-foreground text-sm">
                          {author.display_name}
                        </div>
                        <div className="text-xs text-muted-foreground truncate mt-0.5">
                          {getInstitution(author)}
                        </div>
                      </div>
                      <span className="text-xs bg-secondary px-2 py-0.5 rounded text-secondary-foreground shrink-0 ml-3">
                        {author.works_count} 篇
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : !isSearching ? (
              <div className="px-4 py-3 text-sm text-muted-foreground">
                未找到匹配的作者
              </div>
            ) : (
              <div className="px-4 py-3 text-sm text-muted-foreground flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                搜索中...
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components (tooltip, stat card, etc.)                          */
/* ------------------------------------------------------------------ */

function CompareTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-md text-sm">
      <p className="font-medium text-foreground mb-1">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} style={{ color: entry.color }}>
          {entry.name}: {entry.value} 篇
        </p>
      ))}
    </div>
  );
}

function StatCard({ icon: Icon, label, valueA, valueB, colorClass, borderClass }) {
  return (
    <div className={`${colorClass} ${borderClass} rounded-lg p-4 border`}>
      <div className="flex items-center gap-2 mb-3">
        <Icon size={18} className="text-muted-foreground" />
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
            {(valueA ?? 0).toLocaleString()}
          </div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
            {(valueB ?? 0).toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ComparePage                                                       */
/* ------------------------------------------------------------------ */

function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const idA = searchParams.get('a');
  const idB = searchParams.get('b');

  // Store lightweight selected-author info for chips (before full data loads)
  const [selectedA, setSelectedA] = useState(null);
  const [selectedB, setSelectedB] = useState(null);

  // Full author data from API
  const { data: authorA, isLoading: loadingA, error: errorA } = useAuthor(idA);
  const { data: authorB, isLoading: loadingB, error: errorB } = useAuthor(idB);
  const { data: timelineA = [] } = usePublicationTimeline(idA);
  const { data: timelineB = [] } = usePublicationTimeline(idB);

  // Sync full author data into selected chips (for pre-filled URL params)
  useEffect(() => {
    if (authorA && (!selectedA || selectedA.id !== authorA.id)) {
      setSelectedA({
        id: authorA.id,
        display_name: authorA.display_name,
        institution:
          authorA.primary_institution_name ||
          authorA.last_known_institution_name ||
          null,
      });
    }
  }, [authorA]);

  useEffect(() => {
    if (authorB && (!selectedB || selectedB.id !== authorB.id)) {
      setSelectedB({
        id: authorB.id,
        display_name: authorB.display_name,
        institution:
          authorB.primary_institution_name ||
          authorB.last_known_institution_name ||
          null,
      });
    }
  }, [authorB]);

  // Update URL when selection changes
  const updateParam = useCallback(
    (slot, authorId) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (authorId) {
            next.set(slot, authorId);
          } else {
            next.delete(slot);
          }
          return next;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  const handleSelectA = useCallback(
    (author) => {
      setSelectedA(author);
      updateParam('a', author.id);
    },
    [updateParam]
  );

  const handleSelectB = useCallback(
    (author) => {
      setSelectedB(author);
      updateParam('b', author.id);
    },
    [updateParam]
  );

  const handleClearA = useCallback(() => {
    setSelectedA(null);
    updateParam('a', null);
  }, [updateParam]);

  const handleClearB = useCallback(() => {
    setSelectedB(null);
    updateParam('b', null);
  }, [updateParam]);

  // Set document title
  useEffect(() => {
    if (authorA && authorB) {
      document.title = `对比: ${authorA.display_name} vs ${authorB.display_name} - CoAuthorTrace`;
    } else if (authorA) {
      document.title = `对比: ${authorA.display_name} - CoAuthorTrace`;
    } else {
      document.title = '作者对比 - CoAuthorTrace';
    }
    return () => {
      document.title = 'CoAuthorTrace';
    };
  }, [authorA, authorB]);

  // Merge timelines for the overlay chart
  const mergedTimeline = useMemo(() => {
    if (!timelineA.length && !timelineB.length) return [];

    const yearMap = new Map();
    for (const item of timelineA) {
      yearMap.set(item.year, { year: item.year, authorA: item.count, authorB: 0 });
    }
    for (const item of timelineB) {
      const existing = yearMap.get(item.year);
      if (existing) {
        existing.authorB = item.count;
      } else {
        yearMap.set(item.year, { year: item.year, authorA: 0, authorB: item.count });
      }
    }
    return Array.from(yearMap.values()).sort((a, b) => a.year - b.year);
  }, [timelineA, timelineB]);

  const bothSelected = idA && idB;
  const loading = bothSelected && (loadingA || loadingB);
  const error = bothSelected && (errorA || errorB);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
  };
  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 },
  };

  return (
    <motion.div
      className="space-y-8"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Breadcrumb */}
      <nav className="flex items-center text-sm text-muted-foreground">
        <Link to="/" className="hover:text-primary transition-colors">
          首页
        </Link>
        <ChevronRight size={14} className="mx-2" />
        <span className="text-foreground font-medium">作者对比</span>
      </nav>

      {/* Author Search Selectors */}
      <motion.div
        variants={itemVariants}
        className="bg-card rounded-xl border border-border shadow-sm p-5"
      >
        <h2 className="text-base font-semibold text-foreground mb-4">
          选择要对比的作者
        </h2>
        <div className="flex flex-col md:flex-row gap-4 items-start">
          <AuthorSearchInput
            slot="a"
            selectedAuthor={selectedA}
            onSelect={handleSelectA}
            onClear={handleClearA}
            otherAuthorId={idB}
          />
          <div className="flex items-center justify-center self-center md:mt-8">
            <div className="w-9 h-9 rounded-full bg-muted border border-border flex items-center justify-center">
              <ArrowRightLeft size={16} className="text-muted-foreground" />
            </div>
          </div>
          <AuthorSearchInput
            slot="b"
            selectedAuthor={selectedB}
            onSelect={handleSelectB}
            onClear={handleClearB}
            otherAuthorId={idA}
          />
        </div>
      </motion.div>

      {/* States: loading, error, or not both selected */}
      {!bothSelected && (
        <motion.div
          variants={itemVariants}
          className="bg-card rounded-xl border border-border shadow-sm p-12 text-center"
        >
          <Search className="mx-auto h-12 w-12 text-muted-foreground/30 mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">
            {!idA && !idB
              ? '搜索并选择两位作者开始对比'
              : '请选择第二位作者进行对比'}
          </h3>
          <p className="text-sm text-muted-foreground">
            在上方搜索框中输入作者姓名,选择作者后即可查看对比数据
          </p>
        </motion.div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <Loader2 className="h-10 w-10 animate-spin mb-4 text-primary" />
          <p>正在加载对比数据...</p>
        </div>
      )}

      {error && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <AlertTriangle className="h-12 w-12 text-destructive/50 mb-4" />
          <p className="text-lg font-medium text-foreground">无法加载作者信息</p>
          <Link to="/" className="text-primary hover:underline mt-4">
            返回首页
          </Link>
        </div>
      )}

      {/* Comparison content — only when both authors are loaded */}
      {bothSelected && authorA && authorB && !loading && !error && (
        <>
          {/* Stats Comparison */}
          <motion.div
            variants={itemVariants}
            className="grid grid-cols-1 sm:grid-cols-2 gap-4"
          >
            <StatCard
              icon={BookOpen}
              label="发表论文"
              valueA={authorA?.works_count}
              valueB={authorB?.works_count}
              colorClass="bg-card"
              borderClass="border-border"
            />
            <StatCard
              icon={Quote}
              label="总被引频次"
              valueA={authorA?.cited_by_count}
              valueB={authorB?.cited_by_count}
              colorClass="bg-card"
              borderClass="border-border"
            />
          </motion.div>

          {/* Color Legend */}
          <motion.div
            variants={itemVariants}
            className="flex justify-center gap-6 text-sm text-muted-foreground"
          >
            <span className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-blue-500" />
              {authorA?.display_name}
            </span>
            <span className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-orange-500" />
              {authorB?.display_name}
            </span>
          </motion.div>

          {/* Timeline Chart */}
          {mergedTimeline.length > 0 && (
            <motion.div
              variants={itemVariants}
              className="bg-card rounded-xl border border-border shadow-sm p-6"
            >
              <h2 className="text-lg font-semibold text-foreground mb-6">
                发表趋势对比
              </h2>
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart
                  data={mergedTimeline}
                  margin={{ top: 5, right: 10, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="gradA" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor="hsl(217, 91%, 60%)"
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor="hsl(217, 91%, 60%)"
                        stopOpacity={0}
                      />
                    </linearGradient>
                    <linearGradient id="gradB" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor="hsl(25, 95%, 53%)"
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor="hsl(25, 95%, 53%)"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    className="stroke-border"
                  />
                  <XAxis
                    dataKey="year"
                    tick={{ fontSize: 11 }}
                    className="text-muted-foreground"
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    className="text-muted-foreground"
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip content={<CompareTooltip />} />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="authorA"
                    name={authorA?.display_name || '作者 A'}
                    stroke="hsl(217, 91%, 60%)"
                    strokeWidth={2}
                    fill="url(#gradA)"
                  />
                  <Area
                    type="monotone"
                    dataKey="authorB"
                    name={authorB?.display_name || '作者 B'}
                    stroke="hsl(25, 95%, 53%)"
                    strokeWidth={2}
                    fill="url(#gradB)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </motion.div>
          )}
        </>
      )}
    </motion.div>
  );
}

export default ComparePage;
