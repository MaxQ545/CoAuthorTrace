import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuthor, useAuthorCollaborators, useNetworkMetrics } from '../hooks/queries';
import AuthorCard from '../components/AuthorCard';
import CoAuthoredPapersModal from '../components/CoAuthoredPapersModal';
import PublicationTimeline from '../components/PublicationTimeline';
import ResearchFieldsBadges from '../components/ResearchFieldsBadges';
import { useTimeFilter } from '../contexts/TimeFilterContext';
import {
  Building2,
  MapPin,
  BookOpen,
  Quote,
  Users,
  Network,
  ExternalLink,
  Share2,
  Activity,
  ChevronRight,
  Loader2,
  AlertTriangle
} from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '../lib/utils';

function AuthorPage() {
  const { authorId } = useParams();
  const { timeRange } = useTimeFilter();

  const { data: author, isLoading: authorLoading, error: authorError } = useAuthor(authorId);
  const { data: collaborators = [], isLoading: collabLoading } = useAuthorCollaborators(
    authorId, 30, timeRange.fromYear, timeRange.toYear
  );
  const { data: metrics } = useNetworkMetrics(authorId);

  const loading = authorLoading || collabLoading;
  const error = authorError ? '无法加载作者信息' : null;

  // Modal state for co-authored papers
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedCollaborator, setSelectedCollaborator] = useState({
    id: null,
    name: null
  });

  const handleViewPapers = (collaboratorId, collaboratorName) => {
    setSelectedCollaborator({ id: collaboratorId, name: collaboratorName });
    setModalOpen(true);
  };

  const handleCloseModal = () => {
    setModalOpen(false);
    setSelectedCollaborator({ id: null, name: null });

  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
        <Loader2 className="h-10 w-10 animate-spin mb-4 text-primary" />
        <p>正在加载学者档案...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
        <AlertTriangle className="h-12 w-12 text-destructive/50 mb-4" />
        <p className="text-lg font-medium text-foreground">{error}</p>
        <Link to="/" className="text-primary hover:underline mt-4">
          返回首页
        </Link>
      </div>
    );
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
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
        <span className="text-foreground font-medium truncate">{author?.display_name}</span>
      </nav>

      {/* Author Header Profile */}
      <motion.div variants={itemVariants} className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
        <div className="p-6 md:p-8 flex flex-col md:flex-row gap-8 items-start">
          <div className="flex-1 space-y-4">
            <div>
              <div className="flex flex-wrap items-center gap-3 mb-2">
                <h1 className="text-3xl font-bold text-foreground">
                  {author?.display_name}
                </h1>
                <Link
                  to={`/network/${authorId}`}
                  className="inline-flex items-center gap-1.5 px-3 py-1 bg-primary/10 text-primary text-sm font-medium rounded-full hover:bg-primary/20 transition-colors"
                >
                  <Network size={14} /> 合作网络
                </Link>
              </div>

              <div className="flex items-center gap-2 text-muted-foreground">
                <Building2 size={16} />
                <span className="font-medium">
                  {author?.primary_institution_name || author?.last_known_institution_name || '未知机构'}
                </span>
              </div>
            </div>

            {author?.top_institutions && author.top_institutions.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">常驻机构</div>
                <div className="flex flex-wrap gap-2">
                  {author.top_institutions.map((inst) => (
                    <span
                      key={`${inst.name}-${inst.count}`}
                      className="inline-flex items-center gap-1.5 text-xs bg-secondary/50 text-secondary-foreground px-2.5 py-1 rounded-md border border-border"
                    >
                      <MapPin size={10} />
                      {inst.name}
                      <span className="text-muted-foreground border-l border-border pl-1.5 ml-1">{inst.count}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {author?.research_fields && author.research_fields.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">研究领域</div>
                <ResearchFieldsBadges fields={author.research_fields} maxDisplay={5} showCount={true} />
              </div>
            )}
          </div>

          {/* Stats Cards in Header */}
          <div className="grid grid-cols-2 gap-3 w-full md:w-auto min-w-[300px]">
            <div className="bg-blue-500/5 border border-blue-500/10 rounded-lg p-4 flex flex-col items-center justify-center text-center">
              <BookOpen className="text-blue-600 mb-2" size={20} />
              <div className="text-2xl font-bold text-foreground">
                {author?.works_count || 0}
              </div>
              <div className="text-xs text-muted-foreground">发表论文{author?.all_ids?.length > 1 && ' (合并)'}</div>
            </div>

            <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-lg p-4 flex flex-col items-center justify-center text-center">
              <Quote className="text-emerald-600 mb-2" size={20} />
              <div className="text-2xl font-bold text-foreground">
                {author?.cited_by_count || 0}
              </div>
              <div className="text-xs text-muted-foreground">总被引频次</div>
            </div>

            <div className="bg-purple-500/5 border border-purple-500/10 rounded-lg p-4 flex flex-col items-center justify-center text-center">
              <Users className="text-purple-600 mb-2" size={20} />
              <div className="text-2xl font-bold text-foreground">
                {collaborators.length}
              </div>
              <div className="text-xs text-muted-foreground">核心合作者</div>
            </div>

            <div className="bg-amber-500/5 border border-amber-500/10 rounded-lg p-4 flex flex-col items-center justify-center text-center">
              <Share2 className="text-amber-600 mb-2" size={20} />
              <div className="text-2xl font-bold text-foreground">
                {collaborators.reduce((sum, c) => sum + c.collaboration_count, 0)}
              </div>
              <div className="text-xs text-muted-foreground">合作论文数</div>
            </div>
          </div>
        </div>

        {/* Footer info: IDs */}
        <div className="bg-muted/30 border-t border-border px-6 py-3">
           <details className="group">
            <summary className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer hover:text-primary transition-colors select-none">
              <span className="font-medium">OpenAlex IDs & ORCID</span>
              <span className="bg-muted px-1.5 rounded-full text-[10px]">{author?.all_ids?.length || 1}</span>
              <ChevronRight size={12} className="group-open:rotate-90 transition-transform" />
            </summary>

            <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {author?.all_ids?.map((idInfo) => (
                <div key={idInfo.id} className="flex items-center justify-between text-xs bg-background border border-border rounded p-2">
                  <div className="flex items-center gap-2 overflow-hidden">
                    <code className="bg-muted px-1.5 py-0.5 rounded text-[10px] font-mono shrink-0">{idInfo.id}</code>
                    <span className="text-muted-foreground truncate">{idInfo.works_count} 篇</span>
                  </div>
                  {idInfo.orcid ? (
                    <a
                      href={idInfo.orcid}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-600 hover:underline flex items-center gap-1 shrink-0"
                    >
                      ORCID <ExternalLink size={10} />
                    </a>
                  ) : (
                    <span className="text-muted-foreground/40">No ORCID</span>
                  )}
                </div>
              ))}
            </div>
           </details>
        </div>
      </motion.div>

      {/* Network Metrics */}
      {metrics && Object.keys(metrics).length > 0 && (
        <motion.div variants={itemVariants} className="bg-card rounded-xl border border-border shadow-sm p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div className="flex items-center gap-2">
              <Activity className="text-primary" size={20} />
              <h2 className="text-lg font-semibold text-foreground">
                网络中心性指标
              </h2>
            </div>
            {metrics.institution_name && (
              <span className="text-xs bg-secondary text-secondary-foreground px-3 py-1 rounded-full border border-border">
                范围: {metrics.institution_name}
                {metrics.institution_author_count && ` (${metrics.institution_author_count}人)`}
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {[
              { label: '度中心性', value: metrics.degree_centrality, format: v => `${(v * 100).toFixed(2)}%` },
              { label: 'PageRank', value: metrics.pagerank, format: v => (v * 1000).toFixed(3) },
              { label: '聚类系数', value: metrics.clustering_coefficient, format: v => `${(v * 100).toFixed(1)}%` },
              { label: '中介中心性', value: metrics.betweenness_centrality, format: v => `${(v * 100).toFixed(3)}%` },
              { label: '接近中心性', value: metrics.closeness_centrality, format: v => `${(v * 100).toFixed(2)}%` },
              { label: '特征向量', value: metrics.eigenvector_centrality, format: v => `${(v * 100).toFixed(3)}%` },
            ].map((metric) => metric.value != null && (
              <div key={metric.label} className="bg-secondary/20 rounded-lg p-3 border border-border/50 text-center hover:border-primary/30 transition-colors">
                <div className="text-lg font-bold text-foreground font-mono">
                  {metric.format(metric.value)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">{metric.label}</div>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Publication Timeline */}
      <motion.div variants={itemVariants}>
        <PublicationTimeline
          authorId={authorId}
          fromYear={timeRange.fromYear}
          toYear={timeRange.toYear}
        />
      </motion.div>

      {/* Collaborators List */}
      <motion.div variants={itemVariants} className="bg-card rounded-xl border border-border shadow-sm p-6">
        <h2 className="text-lg font-semibold text-foreground mb-6 flex items-center gap-2">
          <Users size={20} className="text-primary" />
          合作者列表 ({collaborators.length})
        </h2>

        {collaborators.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {collaborators.map((collab, index) => (
              <AuthorCard
                key={collab.id}
                author={collab}
                showCollabCount={true}
                collabCount={collab.collaboration_count}
                rank={index + 1}
                showViewPapersButton={true}
                mainAuthorId={authorId}
                onViewPapers={handleViewPapers}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-12 bg-secondary/10 rounded-lg border border-dashed border-border">
            <Users className="mx-auto h-12 w-12 text-muted-foreground/30 mb-3" />
            <p className="text-muted-foreground">暂无合作者数据</p>
          </div>
        )}
      </motion.div>

      {/* Co-authored papers modal */}
      <CoAuthoredPapersModal
        isOpen={modalOpen}
        onClose={handleCloseModal}
        authorId={authorId}
        authorName={author?.display_name}
        collaboratorId={selectedCollaborator.id}
        collaboratorName={selectedCollaborator.name}
      />
    </motion.div>
  );
}

export default AuthorPage;
