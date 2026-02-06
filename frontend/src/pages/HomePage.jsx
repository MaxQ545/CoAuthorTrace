import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';
import SearchBox from '../components/SearchBox';
import StatsCard from '../components/StatsCard';
import { motion } from 'framer-motion';
import { ArrowRight, Users, BookOpen, Share2, Activity, Zap, Network, Search, Loader2 } from 'lucide-react';

function HomePage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const data = await client.getSystemStats();
        // Map old structure to new structure if needed, or just use as is
        // The API returns: { status: "ok", database: { total_works, ... }, crawl: {...} }
        // We need to flatten it slightly for easy usage
        setStats({
          works_count: data.database.total_works,
          authors_count: data.database.total_authors,
          collaborations_count: data.database.total_collaborations,
          total_relationship_scores: data.database.total_relationship_scores,
          last_crawl_date: data.crawl.last_crawl_date,
          status: data.status
        });
      } catch (error) {
        console.error('Failed to fetch stats:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatsCard
              title="收录论文"
              value={stats.works_count.toLocaleString()}
              icon={<BookOpen size={24} />}
              color="blue"
              delay={0.1}
            />
            <StatsCard
              title="科研学者"
              value={stats.authors_count.toLocaleString()}
              icon={<Users size={24} />}
              color="green"
              delay={0.2}
            />
            <StatsCard
              title="合作关系"
              value={stats.collaborations_count.toLocaleString()}
              icon={<Share2 size={24} />}
              color="purple"
              delay={0.3}
            />
            <StatsCard
              title="关系评分"
              value={stats.total_relationship_scores?.toLocaleString() || '0'}
              icon={<Activity size={24} />}
              color="orange"
              delay={0.4}
            />
          </div>
        ) : (
          <div className="text-center text-destructive bg-destructive/10 p-4 rounded-lg">
            加载统计数据失败，请检查后端服务是否运行。
          </div>
        )}
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
