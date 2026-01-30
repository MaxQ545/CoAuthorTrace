import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import StatsCard from '../components/StatsCard';
import SearchBox from '../components/SearchBox';
import AuthorCard from '../components/AuthorCard';

function HomePage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const data = await api.getSystemStatus();
      setStatus(data);
    } catch (error) {
      console.error('Failed to load status:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (query) => {
    setSearching(true);
    setSearchQuery(query);
    try {
      const data = await api.searchAuthors(query, 20);
      setSearchResults(data.results);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setSearching(false);
    }
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

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="text-center py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          📚 论文合作者追踪系统
        </h1>
        <p className="text-gray-600 mb-8">
          基于 OpenAlex 数据，分析合肥工业大学 CS/AI 领域的学术合作关系
        </p>

        {/* Search Box */}
        <div className="max-w-2xl mx-auto">
          <SearchBox
            onSearch={handleSearch}
            placeholder="输入作者姓名搜索..."
            loading={searching}
          />
        </div>
      </div>

      {/* Stats Cards */}
      {status && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatsCard
            title="论文总数"
            value={status.database.total_works}
            icon="📄"
            color="blue"
          />
          <StatsCard
            title="作者总数"
            value={status.database.total_authors}
            icon="👥"
            color="green"
          />
          <StatsCard
            title="合作关系"
            value={status.database.total_collaborations}
            icon="🤝"
            color="purple"
          />
          <StatsCard
            title="关系评分"
            value={status.database.total_relationship_scores}
            icon="📊"
            color="orange"
          />
        </div>
      )}

      {/* Search Results */}
      {searchResults.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            🔍 搜索结果: "{searchQuery}"
            <span className="text-sm font-normal text-gray-500 ml-2">
              ({searchResults.length} 位作者)
            </span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {searchResults.map((author) => (
              <AuthorCard key={author.id} author={author} />
            ))}
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">🚀 快速开始</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={() => handleSearch('Wang')}
            className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left"
          >
            <div className="font-medium text-gray-900">搜索 "Wang"</div>
            <div className="text-sm text-gray-500">查看姓王的作者</div>
          </button>
          <button
            onClick={() => handleSearch('Zhang')}
            className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-left"
          >
            <div className="font-medium text-gray-900">搜索 "Zhang"</div>
            <div className="text-sm text-gray-500">查看姓张的作者</div>
          </button>
          <button
            onClick={() => navigate('/network')}
            className="p-4 border border-blue-200 bg-blue-50 rounded-lg hover:bg-blue-100 text-left"
          >
            <div className="font-medium text-blue-700">🕸️ 浏览合作网络</div>
            <div className="text-sm text-blue-600">可视化作者合作关系</div>
          </button>
        </div>
      </div>

      {/* System Info */}
      {status && (
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
          <div className="flex items-center justify-between">
            <div>
              系统状态: <span className="text-green-600 font-medium">● {status.status}</span>
            </div>
            <div>
              最后爬取: {status.crawl.last_crawl_date || '暂无'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default HomePage;
