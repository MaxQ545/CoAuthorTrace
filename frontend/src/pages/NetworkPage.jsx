import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import NetworkGraph from '../components/NetworkGraph';
import SearchBox from '../components/SearchBox';
import { useTimeFilter } from '../contexts/TimeFilterContext';

function NetworkPage() {
  const { authorId } = useParams();
  const navigate = useNavigate();
  const { timeRange } = useTimeFilter();
  const [author, setAuthor] = useState(null);
  const [collaborators, setCollaborators] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (authorId) {
      loadAuthorNetwork(authorId);
    }
  }, [authorId, timeRange.fromYear, timeRange.toYear]);

  const loadAuthorNetwork = async (id) => {
    setLoading(true);
    try {
      const [authorData, collabData] = await Promise.all([
        api.getAuthor(id),
        api.getAuthorCollaborators(id, 50, timeRange.fromYear, timeRange.toYear),
      ]);

      setAuthor(authorData);
      setCollaborators(collabData.collaborators || []);

      // Build graph data
      const graphNodes = [
        {
          id: authorData.id,
          label: authorData.display_name,
          papers: authorData.works_count,
          citations: authorData.cited_by_count,
        },
      ];

      const graphEdges = [];

      for (const collab of collabData.collaborators || []) {
        graphNodes.push({
          id: collab.id,
          label: collab.display_name,
          papers: collab.works_count,
          citations: collab.cited_by_count,
          collabCount: collab.collaboration_count,
        });

        graphEdges.push({
          from: authorData.id,
          to: collab.id,
          count: collab.collaboration_count,
          weight: collab.collaboration_count,
        });
      }

      setNodes(graphNodes);
      setEdges(graphEdges);
    } catch (error) {
      console.error('Failed to load network:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (query) => {
    setSearching(true);
    try {
      const data = await api.searchAuthors(query, 10);
      setSearchResults(data.results);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setSearching(false);
    }
  };

  const handleNodeClick = (nodeId) => {
    navigate(`/author/${nodeId}`);
  };

  const selectAuthor = (id) => {
    navigate(`/network/${id}`);
    setSearchResults([]);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">
          🕸️ 合作网络可视化
        </h1>
      </div>

      {/* Search */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          选择一位作者查看其合作网络:
        </label>
        <SearchBox
          onSearch={handleSearch}
          placeholder="输入作者姓名搜索..."
          loading={searching}
        />

        {/* Search Results Dropdown */}
        {searchResults.length > 0 && (
          <div className="mt-2 border border-gray-200 rounded-lg divide-y max-h-64 overflow-auto">
            {searchResults.map((result) => (
              <button
                key={result.id}
                onClick={() => selectAuthor(result.id)}
                className="w-full px-4 py-2 text-left hover:bg-gray-50 flex justify-between items-center"
              >
                <span className="font-medium">{result.display_name}</span>
                <span className="text-sm text-gray-500">
                  {result.works_count} 篇论文
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Current Author Info */}
      {author && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-blue-700 font-medium">当前查看: </span>
              <span className="text-blue-900 font-bold">{author.display_name}</span>
              <span className="text-blue-600 ml-2">
                ({collaborators.length} 位合作者)
              </span>
            </div>
            <button
              onClick={() => navigate(`/author/${author.id}`)}
              className="text-sm text-blue-600 hover:underline"
            >
              查看详情 →
            </button>
          </div>
        </div>
      )}

      {/* Network Graph */}
      {loading ? (
        <div className="flex items-center justify-center h-[500px] bg-white rounded-lg border">
          <div className="text-center">
            <div className="animate-spin text-4xl mb-4">⏳</div>
            <p className="text-gray-600">正在加载网络数据...</p>
          </div>
        </div>
      ) : nodes.length > 0 ? (
        <NetworkGraph
          nodes={nodes}
          edges={edges}
          centerNodeId={authorId}
          onNodeClick={handleNodeClick}
        />
      ) : (
        <div className="flex items-center justify-center h-[500px] bg-white rounded-lg border">
          <div className="text-center text-gray-500">
            <div className="text-4xl mb-4">🔍</div>
            <p>请搜索并选择一位作者来查看其合作网络</p>
          </div>
        </div>
      )}

      {/* Collaborator List */}
      {collaborators.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="font-semibold text-gray-900 mb-3">
            合作者列表 (按合作次数排序)
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
            {collaborators.slice(0, 20).map((collab, index) => (
              <button
                key={collab.id}
                onClick={() => selectAuthor(collab.id)}
                className="text-left px-3 py-2 rounded border border-gray-200 hover:bg-gray-50 text-sm"
              >
                <div className="flex items-center space-x-2">
                  <span className="text-gray-400">{index + 1}.</span>
                  <span className="font-medium truncate">{collab.display_name}</span>
                </div>
                <div className="text-xs text-gray-500 ml-5">
                  {collab.collaboration_count} 次合作
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
        <div className="font-medium mb-2">图例说明:</div>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center space-x-2">
            <span className="w-4 h-4 rounded-full bg-blue-500"></span>
            <span>中心作者</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-4 h-4 rounded-full bg-blue-300"></span>
            <span>合作者</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-8 h-0.5 bg-gray-400"></span>
            <span>合作关系 (线越粗合作越多)</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default NetworkPage;
