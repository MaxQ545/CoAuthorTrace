import { useState, useEffect } from 'react';
import api from '../api/client';
import { useTimeFilter } from '../contexts/TimeFilterContext';

function CoAuthoredPapersModal({
  isOpen,
  onClose,
  authorId,
  authorName,
  collaboratorId,
  collaboratorName
}) {
  const { timeRange } = useTimeFilter();
  const [papers, setPapers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Pagination and sorting state
  const [offset, setOffset] = useState(0);
  const [sortBy, setSortBy] = useState('publication_date');
  const [sortOrder, setSortOrder] = useState('desc');
  const limit = 20;

  useEffect(() => {
    if (isOpen && authorId && collaboratorId) {
      loadPapers();
    }
  }, [isOpen, authorId, collaboratorId, offset, sortBy, sortOrder, timeRange.fromYear, timeRange.toYear]);

  // Reset when modal opens with new collaborator
  useEffect(() => {
    if (isOpen) {
      setOffset(0);
    }
  }, [isOpen, collaboratorId]);

  const loadPapers = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await api.getCoAuthoredPapers(
        authorId,
        collaboratorId,
        limit,
        offset,
        sortBy,
        sortOrder,
        timeRange.fromYear,
        timeRange.toYear
      );
      setPapers(data.papers);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load co-authored papers:', err);
      setError('无法加载论文列表');
    } finally {
      setLoading(false);
    }
  };

  const handleSortChange = (newSortBy) => {
    if (newSortBy === sortBy) {
      // Toggle order if same field
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(newSortBy);
      setSortOrder('desc');
    }
    setOffset(0);
  };

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              合作论文
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {authorName} 与 {collaboratorName} 共同发表的论文
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Sort controls */}
        <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex items-center space-x-4">
          <span className="text-sm text-gray-600">排序:</span>
          <button
            onClick={() => handleSortChange('publication_date')}
            className={`text-sm px-3 py-1 rounded ${
              sortBy === 'publication_date'
                ? 'bg-blue-100 text-blue-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            日期 {sortBy === 'publication_date' && (sortOrder === 'desc' ? '↓' : '↑')}
          </button>
          <button
            onClick={() => handleSortChange('cited_by_count')}
            className={`text-sm px-3 py-1 rounded ${
              sortBy === 'cited_by_count'
                ? 'bg-blue-100 text-blue-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            引用数 {sortBy === 'cited_by_count' && (sortOrder === 'desc' ? '↓' : '↑')}
          </button>
          <button
            onClick={() => handleSortChange('title')}
            className={`text-sm px-3 py-1 rounded ${
              sortBy === 'title'
                ? 'bg-blue-100 text-blue-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            标题 {sortBy === 'title' && (sortOrder === 'desc' ? '↓' : '↑')}
          </button>
          <span className="text-sm text-gray-500 ml-auto">
            共 {total} 篇论文
          </span>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <div className="text-center">
                <div className="animate-spin text-2xl mb-2">⏳</div>
                <p className="text-gray-600 text-sm">加载中...</p>
              </div>
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <div className="text-2xl mb-2">😕</div>
              <p className="text-gray-600">{error}</p>
              <button
                onClick={loadPapers}
                className="mt-2 text-blue-600 hover:underline text-sm"
              >
                重试
              </button>
            </div>
          ) : papers.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              暂无论文数据
            </div>
          ) : (
            <div className="space-y-3">
              {papers.map((paper, index) => (
                <div
                  key={paper.id}
                  className="p-4 border border-gray-200 rounded-lg hover:shadow-sm transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs text-gray-400">
                          {offset + index + 1}.
                        </span>
                        <h3 className="font-medium text-gray-900">
                          {paper.title}
                        </h3>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-600">
                        {paper.publication_date && (
                          <span>
                            📅 {paper.publication_date}
                          </span>
                        )}
                        {paper.source_name && (
                          <span className="truncate max-w-xs" title={paper.source_name}>
                            📖 {paper.source_name}
                          </span>
                        )}
                        <span>
                          📊 {paper.cited_by_count} 次引用
                        </span>
                        {paper.is_open_access && (
                          <span className="text-green-600">
                            🔓 开放获取
                          </span>
                        )}
                      </div>
                    </div>
                    {paper.doi && (
                      <a
                        href={`https://doi.org/${paper.doi}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-4 text-xs px-3 py-1 bg-blue-100 text-blue-700 rounded-full hover:bg-blue-200 whitespace-nowrap"
                      >
                        DOI
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-gray-200 flex items-center justify-between">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className={`px-3 py-1 rounded text-sm ${
                offset === 0
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              上一页
            </button>
            <span className="text-sm text-gray-600">
              第 {currentPage} / {totalPages} 页
            </span>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={currentPage >= totalPages}
              className={`px-3 py-1 rounded text-sm ${
                currentPage >= totalPages
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              下一页
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default CoAuthoredPapersModal;
