import { useEffect, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuthor, usePublicationTimeline } from '../hooks/queries';
import {
  Building2,
  BookOpen,
  Quote,
  Loader2,
  AlertTriangle,
  ChevronRight,
  ArrowRightLeft,
  Search,
} from 'lucide-react';
import { motion } from 'framer-motion';
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

function AuthorHeader({ author, color, label }) {
  const colorStyles = color === 'blue'
    ? 'border-blue-500/30 bg-blue-500/5'
    : 'border-orange-500/30 bg-orange-500/5';
  const dotColor = color === 'blue' ? 'bg-blue-500' : 'bg-orange-500';

  return (
    <div className={`rounded-xl border ${colorStyles} p-5 flex-1 min-w-0`}>
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-3 h-3 rounded-full ${dotColor}`} />
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {label}
        </span>
      </div>
      <Link
        to={`/author/${author.id}`}
        className="text-xl font-bold text-foreground hover:text-primary transition-colors block truncate"
      >
        {author.display_name}
      </Link>
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground mt-1">
        <Building2 size={14} />
        <span className="truncate">
          {author.primary_institution_name || author.last_known_institution_name || '未知机构'}
        </span>
      </div>
    </div>
  );
}

function PromptAddSecond({ existingAuthorId }) {
  return (
    <div className="space-y-6">
      <nav className="flex items-center text-sm text-muted-foreground">
        <Link to="/" className="hover:text-primary transition-colors">首页</Link>
        <ChevronRight size={14} className="mx-2" />
        <span className="text-foreground font-medium">作者对比</span>
      </nav>

      <div className="bg-card rounded-xl border border-border shadow-sm p-12 text-center">
        <Search className="mx-auto h-12 w-12 text-muted-foreground/30 mb-4" />
        <h2 className="text-xl font-semibold text-foreground mb-2">选择第二位作者进行对比</h2>
        <p className="text-muted-foreground mb-6">
          请通过搜索页面找到第二位作者,然后在其个人页面点击"对比"按钮
        </p>
        <div className="flex justify-center gap-3">
          <Link
            to="/authors/search"
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
          >
            <Search size={16} />
            搜索作者
          </Link>
          {existingAuthorId && (
            <Link
              to={`/author/${existingAuthorId}`}
              className="inline-flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium"
            >
              返回作者页
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

function ComparePage() {
  const [searchParams] = useSearchParams();
  const idA = searchParams.get('a');
  const idB = searchParams.get('b');

  const { data: authorA, isLoading: loadingA, error: errorA } = useAuthor(idA);
  const { data: authorB, isLoading: loadingB, error: errorB } = useAuthor(idB);
  const { data: timelineA = [] } = usePublicationTimeline(idA);
  const { data: timelineB = [] } = usePublicationTimeline(idB);

  // Set document title
  useEffect(() => {
    if (authorA && authorB) {
      document.title = `对比: ${authorA.display_name} vs ${authorB.display_name} - CoAuthorTrace`;
    } else if (authorA) {
      document.title = `对比: ${authorA.display_name} - CoAuthorTrace`;
    } else {
      document.title = '作者对比 - CoAuthorTrace';
    }
    return () => { document.title = 'CoAuthorTrace'; };
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

  // Handle case: only one author param
  if (!idA && !idB) {
    return <PromptAddSecond />;
  }
  if (idA && !idB) {
    return <PromptAddSecond existingAuthorId={idA} />;
  }
  if (!idA && idB) {
    return <PromptAddSecond existingAuthorId={idB} />;
  }

  const loading = loadingA || loadingB;
  const error = errorA || errorB;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
        <Loader2 className="h-10 w-10 animate-spin mb-4 text-primary" />
        <p>正在加载对比数据...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
        <AlertTriangle className="h-12 w-12 text-destructive/50 mb-4" />
        <p className="text-lg font-medium text-foreground">无法加载作者信息</p>
        <Link to="/" className="text-primary hover:underline mt-4">返回首页</Link>
      </div>
    );
  }

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
        <Link to="/" className="hover:text-primary transition-colors">首页</Link>
        <ChevronRight size={14} className="mx-2" />
        <span className="text-foreground font-medium">作者对比</span>
      </nav>

      {/* Author Headers */}
      <motion.div variants={itemVariants} className="flex flex-col md:flex-row gap-4 items-stretch">
        {authorA && <AuthorHeader author={authorA} color="blue" label="作者 A" />}
        <div className="flex items-center justify-center">
          <div className="w-10 h-10 rounded-full bg-muted border border-border flex items-center justify-center">
            <ArrowRightLeft size={18} className="text-muted-foreground" />
          </div>
        </div>
        {authorB && <AuthorHeader author={authorB} color="orange" label="作者 B" />}
      </motion.div>

      {/* Stats Comparison */}
      <motion.div variants={itemVariants} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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

      {/* Color Legend for stats */}
      <motion.div variants={itemVariants} className="flex justify-center gap-6 text-sm text-muted-foreground">
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
        <motion.div variants={itemVariants} className="bg-card rounded-xl border border-border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-foreground mb-6">发表趋势对比</h2>
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={mergedTimeline} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="gradA" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(217, 91%, 60%)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(217, 91%, 60%)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradB" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(25, 95%, 53%)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(25, 95%, 53%)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
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
    </motion.div>
  );
}

export default ComparePage;
