import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api/client';
import AuthorCard from '../components/AuthorCard';
import CoAuthoredPapersModal from '../components/CoAuthoredPapersModal';
import { useTimeFilter } from '../contexts/TimeFilterContext';

function AuthorPage() {
  const { authorId } = useParams();
  const { timeRange } = useTimeFilter();
  const [author, setAuthor] = useState(null);
  const [collaborators, setCollaborators] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Modal state for co-authored papers
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedCollaborator, setSelectedCollaborator] = useState({
    id: null,
    name: null
  });

  useEffect(() => {
    loadAuthorData();
  }, [authorId, timeRange.fromYear, timeRange.toYear]);

  const loadAuthorData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [authorData, collabData] = await Promise.all([
        api.getAuthor(authorId),
        api.getAuthorCollaborators(authorId, 30, timeRange.fromYear, timeRange.toYear),
      ]);

      setAuthor(authorData);
      setCollaborators(collabData.collaborators || []);

      // Load metrics separately (may fail)
      try {
        const metricsData = await api.getAuthorNetworkMetrics(authorId);
        setMetrics(metricsData.metrics);
      } catch (e) {
        console.warn('Failed to load metrics:', e);
      }
    } catch (error) {
      console.error('Failed to load author:', error);
      setError('无法加载作者信息');
    } finally {
      setLoading(false);
    }
  };

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
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin text-4xl mb-4">⏳</div>
          <p className="text-gray-600">加载中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-4xl mb-4">😕</div>
        <p className="text-gray-600">{error}</p>
        <Link to="/" className="text-blue-600 hover:underline mt-4 inline-block">
          返回首页
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="text-sm text-gray-500">
        <Link to="/" className="hover:text-blue-600">首页</Link>
        <span className="mx-2">/</span>
        <span className="text-gray-900">{author?.display_name}</span>
      </nav>

      {/* Author Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {author?.display_name}
            </h1>
            {(author?.primary_institution_name || author?.last_known_institution_name) && (
              <p className="text-gray-600 mt-2">
                🏛️ {author.primary_institution_name || author.last_known_institution_name}
              </p>
            )}
            {author?.top_institutions && author.top_institutions.length > 0 && (
              <div className="mt-3">
                <div className="text-xs text-gray-500 mb-2">高频机构</div>
                <div className="flex flex-wrap gap-2">
                  {author.top_institutions.map((inst) => (
                    <span
                      key={`${inst.name}-${inst.count}`}
                      className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded-full"
                    >
                      {inst.name} · {inst.count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <Link
            to={`/network/${authorId}`}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            🕸️ 查看合作网络
          </Link>
        </div>

        {/* All IDs and ORCIDs */}
        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">
            🔗 OpenAlex ID 与 ORCID {author?.all_ids?.length > 1 && `(共 ${author.all_ids.length} 个合并记录)`}
          </h3>
          {author?.all_ids && author.all_ids.length > 0 ? (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {author.all_ids.map((idInfo, index) => (
                <div key={idInfo.id} className="flex items-center justify-between text-sm py-1 border-b border-gray-200 last:border-0">
                  <div className="flex items-center space-x-2">
                    <span className="text-gray-400 w-6">{index + 1}.</span>
                    <code className="bg-gray-200 px-2 py-0.5 rounded text-xs">{idInfo.id}</code>
                    <span className="text-gray-500">({idInfo.works_count} 篇)</span>
                  </div>
                  <div className="text-right">
                    {idInfo.orcid ? (
                      <a
                        href={idInfo.orcid}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline text-xs"
                      >
                        {idInfo.orcid.replace('https://orcid.org/', '')}
                      </a>
                    ) : (
                      <span className="text-gray-400 text-xs">无 ORCID</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm">
              <div className="flex items-center justify-between py-1">
                <code className="bg-gray-200 px-2 py-0.5 rounded text-xs">{author?.id}</code>
                {author?.orcid ? (
                  <a
                    href={author.orcid}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline text-xs"
                  >
                    {author.orcid.replace('https://orcid.org/', '')}
                  </a>
                ) : (
                  <span className="text-gray-400 text-xs">无 ORCID</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <div className="bg-blue-50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">
              {author?.works_count || 0}
            </div>
            <div className="text-sm text-blue-600">论文数{author?.all_ids?.length > 1 && ' (合并)'}</div>
          </div>
          <div className="bg-green-50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-green-600">
              {author?.cited_by_count || 0}
            </div>
            <div className="text-sm text-green-600">被引次数</div>
          </div>
          <div className="bg-purple-50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-purple-600">
              {collaborators.length}
            </div>
            <div className="text-sm text-purple-600">合作者数</div>
          </div>
          <div className="bg-orange-50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-orange-600">
              {collaborators.reduce((sum, c) => sum + c.collaboration_count, 0)}
            </div>
            <div className="text-sm text-orange-600">合作论文</div>
          </div>
        </div>
      </div>

      {/* Network Metrics */}
      {metrics && Object.keys(metrics).length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              📊 网络中心性指标
            </h2>
            {metrics.institution_name && (
              <span className="text-xs bg-blue-50 text-blue-600 px-2 py-1 rounded">
                机构内计算: {metrics.institution_name}
                {metrics.institution_author_count && ` (${metrics.institution_author_count}人)`}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 mb-4">
            以下指标在同一机构内的合作网络中计算，用于衡量作者在机构内的学术影响力和合作地位
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {metrics.degree_centrality != null && (
              <div className="text-center">
                <div className="text-xl font-bold text-gray-900">
                  {(metrics.degree_centrality * 100).toFixed(2)}%
                </div>
                <div className="text-sm text-gray-500">度中心性</div>
              </div>
            )}
            {metrics.pagerank != null && (
              <div className="text-center">
                <div className="text-xl font-bold text-gray-900">
                  {(metrics.pagerank * 1000).toFixed(3)}
                </div>
                <div className="text-sm text-gray-500">PageRank (×1000)</div>
              </div>
            )}
            {metrics.clustering_coefficient != null && (
              <div className="text-center">
                <div className="text-xl font-bold text-gray-900">
                  {(metrics.clustering_coefficient * 100).toFixed(1)}%
                </div>
                <div className="text-sm text-gray-500">聚类系数</div>
              </div>
            )}
            {metrics.betweenness_centrality != null && (
              <div className="text-center">
                <div className="text-xl font-bold text-gray-900">
                  {(metrics.betweenness_centrality * 100).toFixed(3)}%
                </div>
                <div className="text-sm text-gray-500">中介中心性</div>
              </div>
            )}
            {metrics.closeness_centrality != null && (
              <div className="text-center">
                <div className="text-xl font-bold text-gray-900">
                  {(metrics.closeness_centrality * 100).toFixed(2)}%
                </div>
                <div className="text-sm text-gray-500">接近中心性</div>
              </div>
            )}
            {metrics.eigenvector_centrality != null && (
              <div className="text-center">
                <div className="text-xl font-bold text-gray-900">
                  {(metrics.eigenvector_centrality * 100).toFixed(3)}%
                </div>
                <div className="text-sm text-gray-500">特征向量中心性</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Collaborators */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          🤝 合作者 ({collaborators.length})
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
          <p className="text-gray-500 text-center py-8">暂无合作者数据</p>
        )}
      </div>

      {/* Co-authored papers modal */}
      <CoAuthoredPapersModal
        isOpen={modalOpen}
        onClose={handleCloseModal}
        authorId={authorId}
        authorName={author?.display_name}
        collaboratorId={selectedCollaborator.id}
        collaboratorName={selectedCollaborator.name}
      />
    </div>
  );
}

export default AuthorPage;
