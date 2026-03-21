import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useSystemStats } from '../hooks/queries';
import SearchBox from '../components/SearchBox';
import StatsCard from '../components/StatsCard';
import { motion } from 'framer-motion';
import { ArrowRight, ArrowRightLeft, Users, BookOpen, Share2, Activity, Zap, Network, Search, Loader2, Trophy } from 'lucide-react';

/** Format a number with commas: 1993418 → "1,993,418" */
function formatNumber(n) {
  if (n == null) return '0';
  return Number(n).toLocaleString('en-US');
}

/** Hook that counts from 0 to `target` over ~1 second using rAF */
function useCountUp(target, duration = 1000) {
  const [value, setValue] = useState(0);
  const rafRef = useRef(null);

  useEffect(() => {
    if (target == null || target === 0) {
      setValue(0);
      return;
    }

    const num = Number(target);
    if (isNaN(num)) { setValue(0); return; }

    let start = null;
    const step = (timestamp) => {
      if (!start) start = timestamp;
      const progress = Math.min((timestamp - start) / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * num));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(step);
      }
    };

    rafRef.current = requestAnimationFrame(step);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [target, duration]);

  return value;
}

/** Format last_crawl_date into a human-readable string */
function formatLastUpdated(dateStr) {
  if (!dateStr) return '暂无记录';
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins} 分钟前`;
    if (diffHours < 24) return `${diffHours} 小时前`;
    if (diffDays < 7) return `${diffDays} 天前`;

    return date.toLocaleDateString('zh-CN', {
      year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch {
    return dateStr;
  }
}

const quickActions = [
  {
    title: '搜索学者',
    description: '按姓名查找科研人员，探索其学术成果与合作关系',
    to: '/authors/search',
    icon: Search,
    color: 'blue',
  },
  {
    title: '机构排行',
    description: '查看各机构科研产出排名与学术影响力对比',
    to: '/ranking',
    icon: Trophy,
    color: 'amber',
  },
  {
    title: '合作网络',
    description: '可视化探索学者间的协作图谱与学术圈子',
    to: '/network',
    icon: Network,
    color: 'purple',
  },
  {
    title: '学者对比',
    description: '对比分析多位学者的研究方向与合作模式',
    to: '/compare',
    icon: ArrowRightLeft,
    color: 'emerald',
  },
];

const actionColorStyles = {
  blue: {
    iconBg: 'bg-blue-100 dark:bg-blue-900/30',
    iconText: 'text-blue-600 dark:text-blue-400',
    hoverBorder: 'hover:border-blue-200 dark:hover:border-blue-800',
  },
  amber: {
    iconBg: 'bg-amber-100 dark:bg-amber-900/30',
    iconText: 'text-amber-600 dark:text-amber-400',
    hoverBorder: 'hover:border-amber-200 dark:hover:border-amber-800',
  },
  purple: {
    iconBg: 'bg-purple-100 dark:bg-purple-900/30',
    iconText: 'text-purple-600 dark:text-purple-400',
    hoverBorder: 'hover:border-purple-200 dark:hover:border-purple-800',
  },
  emerald: {
    iconBg: 'bg-emerald-100 dark:bg-emerald-900/30',
    iconText: 'text-emerald-600 dark:text-emerald-400',
    hoverBorder: 'hover:border-emerald-200 dark:hover:border-emerald-800',
  },
};

function AnimatedStatValue({ target }) {
  const animated = useCountUp(target);
  return formatNumber(animated);
}

function HomePage() {
  const navigate = useNavigate();
  const { data: stats, isLoading: loading } = useSystemStats();

  useEffect(() => {
    document.title = 'CoAuthorTrace - 学术合作者追踪系统';
    return () => { document.title = '论文合作者追踪系统'; };
  }, []);

  const handleSearch = (query) => {
    navigate(`/authors/search?q=${encodeURIComponent(query)}`);
  };

  return (
    <div className="space-y-16 pb-12">
      {/* Hero Section */}
      <section className="relative pt-12 pb-20 md:pt-20 md:pb-28 text-center px-4">
        {/* Background Decorative Elements */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full max-w-5xl -z-10 opacity-30 dark:opacity-20 pointer-events-none">
          <div className="absolute top-[-10%] left-[10%] w-72 h-72 bg-blue-400/30 rounded-full blur-[100px] animate-pulse-slow" />
          <div className="absolute bottom-[10%] right-[10%] w-72 h-72 bg-purple-400/30 rounded-full blur-[100px] animate-pulse-slow" style={{ animationDelay: '1.5s' }} />
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="space-y-8 max-w-4xl mx-auto"
        >
          <div className="inline-flex items-center rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm text-primary font-medium mb-2 backdrop-blur-sm">
            <span className="flex h-2 w-2 rounded-full bg-primary mr-2 animate-pulse"></span>
            OpenAlex 数据驱动
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-foreground drop-shadow-sm">
            发现学术界的 <br className="hidden md:block" />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 dark:from-blue-400 dark:via-indigo-400 dark:to-purple-400">
              隐性合作网络
            </span>
          </h1>

          <p className="text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            基于大规模论文数据的深度分析，揭示科研人员之间的真实协作关系与学术影响力网络。
          </p>

          <div className="pt-8 w-full max-w-2xl mx-auto">
            <SearchBox onSearch={handleSearch} placeholder="输入作者姓名，探索学术网络..." />
          </div>

        </motion.div>
      </section>

      {/* Stats Grid */}
      <section className="container mx-auto px-4">
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-32 bg-muted/50 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : stats ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <StatsCard
                title="收录论文"
                value={<AnimatedStatValue target={stats.works_count} />}
                icon={<BookOpen size={24} />}
                color="blue"
                delay={0.1}
              />
              <StatsCard
                title="科研学者"
                value={<AnimatedStatValue target={stats.authors_count} />}
                icon={<Users size={24} />}
                color="green"
                delay={0.2}
              />
              <StatsCard
                title="合作关系"
                value={<AnimatedStatValue target={stats.collaborations_count} />}
                icon={<Share2 size={24} />}
                color="purple"
                delay={0.3}
              />
              <StatsCard
                title="关系评分"
                value={<AnimatedStatValue target={stats.total_relationship_scores || 0} />}
                icon={<Activity size={24} />}
                color="orange"
                delay={0.4}
              />
            </div>
            {/* Last Updated Timestamp */}
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="text-center text-sm text-muted-foreground"
            >
              数据最后更新: {formatLastUpdated(stats.last_crawl_date)}
            </motion.p>
          </div>
        ) : (
          <div className="text-center text-destructive bg-destructive/10 p-4 rounded-lg">
            加载统计数据失败，请检查后端服务是否运行。
          </div>
        )}
      </section>

      {/* Quick Actions */}
      <section className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-2xl font-bold text-foreground text-center mb-8">快速开始</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {quickActions.map((action, i) => {
              const colors = actionColorStyles[action.color];
              const Icon = action.icon;
              return (
                <motion.div
                  key={action.to}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                >
                  <Link
                    to={action.to}
                    className={`group block p-6 rounded-xl border border-border bg-card hover:bg-accent/50 ${colors.hoverBorder} shadow-sm hover:shadow-md transition-all duration-300`}
                  >
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${colors.iconBg} ${colors.iconText}`}>
                      <Icon size={24} />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-1 group-hover:text-primary transition-colors">
                      {action.title}
                    </h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {action.description}
                    </p>
                    <div className="mt-3 flex items-center text-sm font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                      前往 <ArrowRight size={14} className="ml-1" />
                    </div>
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      </section>

      {/* Features/Info Section */}
      <section className="container mx-auto px-4 py-12 border-t border-border">
        <div className="grid md:grid-cols-3 gap-8 text-center md:text-left">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="space-y-4 p-6 rounded-2xl bg-secondary/10 hover:bg-secondary/30 border border-transparent hover:border-border transition-all duration-300"
          >
            <div className="w-12 h-12 bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 rounded-xl flex items-center justify-center mx-auto md:mx-0">
              <Zap size={24} />
            </div>
            <h3 className="text-xl font-bold text-foreground">实时追踪</h3>
            <p className="text-muted-foreground leading-relaxed">
              持续监控 OpenAlex 数据更新，利用智能爬虫技术，及时捕获最新的论文发表与合作动态，保持数据鲜活。
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="space-y-4 p-6 rounded-2xl bg-secondary/10 hover:bg-secondary/30 border border-transparent hover:border-border transition-all duration-300"
          >
            <div className="w-12 h-12 bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400 rounded-xl flex items-center justify-center mx-auto md:mx-0">
              <Activity size={24} />
            </div>
            <h3 className="text-xl font-bold text-foreground">加权分析</h3>
            <p className="text-muted-foreground leading-relaxed">
              独创的合作紧密度算法，综合考量作者署名顺序、合作频率与时间衰减因子，精准量化每一对学者的学术亲密度。
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3 }}
            className="space-y-4 p-6 rounded-2xl bg-secondary/10 hover:bg-secondary/30 border border-transparent hover:border-border transition-all duration-300"
          >
            <div className="w-12 h-12 bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400 rounded-xl flex items-center justify-center mx-auto md:mx-0">
              <Network size={24} />
            </div>
            <h3 className="text-xl font-bold text-foreground">图谱可视化</h3>
            <p className="text-muted-foreground leading-relaxed">
              基于 Force-Directed 布局的交互式网络图谱，直观展示学者间的学术圈子、核心影响力节点及跨学科合作路径。
            </p>
          </motion.div>
        </div>
      </section>

      {/* System Status Footer */}
      {stats && (
        <div className="container mx-auto px-4 pb-8 text-center text-sm text-muted-foreground">
          <div className="inline-flex items-center gap-6 px-6 py-3 rounded-full bg-secondary/30 border border-border">
            <span className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              系统运行正常
            </span>
            <span className="w-px h-4 bg-border"></span>
            <span>最后更新: {stats.last_crawl_date || '刚刚'}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default HomePage;
