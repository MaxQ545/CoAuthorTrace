import { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuthor, useAuthorCollaborators } from '../hooks/queries';
import api from '../api/client';
import NetworkGraph from '../components/NetworkGraph';
import SearchBox from '../components/SearchBox';
import { useTimeFilter } from '../contexts/TimeFilterContext';
import { Network, Users, User, ArrowRight, Loader2, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../lib/utils';

function NetworkPage() {
  const { authorId } = useParams();
  const navigate = useNavigate();
  const { timeRange } = useTimeFilter();
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const searchRef = useRef(null);

  const { data: author, isLoading: authorLoading } = useAuthor(authorId);
  const { data: collaborators = [], isLoading: collabLoading } = useAuthorCollaborators(
    authorId, 50, timeRange.fromYear, timeRange.toYear
  );

  const loading = (authorLoading || collabLoading) && !!authorId;

  // Build graph data from query results
  const { nodes, edges } = useMemo(() => {
    if (!author || collaborators.length === 0) return { nodes: [], edges: [] };

    const graphNodes = [
      {
        id: author.id,
        label: author.display_name,
        papers: author.works_count,
        citations: author.cited_by_count,
      },
    ];

    const graphEdges = [];

    for (const collab of collaborators) {
      graphNodes.push({
        id: collab.id,
        label: collab.display_name,
        papers: collab.works_count,
        citations: collab.cited_by_count,
        collabCount: collab.collaboration_count,
      });

      graphEdges.push({
        from: author.id,
        to: collab.id,
        count: collab.collaboration_count,
        weight: collab.collaboration_count,
      });
    }

    return { nodes: graphNodes, edges: graphEdges };
  }, [author, collaborators]);

  // Close search results when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setSearchResults([]);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [searchRef]);

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
    <div className="space-y-6 animate-fade-in h-[calc(100vh-140px)] flex flex-col">
      {/* Header & Search */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Network className="text-primary" />
            合作网络可视化
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            探索作者之间的学术合作关系与社群结构
          </p>
        </div>

        <div className="relative w-full md:w-96 z-20" ref={searchRef}>
          <SearchBox
            onSearch={handleSearch}
            placeholder="搜索作者以生成网络..."
            loading={searching}
          />

          <AnimatePresence>
            {searchResults.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="absolute top-full left-0 right-0 mt-2 bg-popover border border-border rounded-xl shadow-xl overflow-hidden max-h-80 overflow-y-auto z-50"
              >
                {searchResults.map((result) => (
                  <button
                    key={result.id}
                    onClick={() => selectAuthor(result.id)}
                    className="w-full px-4 py-3 text-left hover:bg-accent/50 flex justify-between items-center transition-colors border-b border-border/50 last:border-0"
                  >
                    <div>
                      <div className="font-medium text-foreground">{result.display_name}</div>
                      <div className="text-xs text-muted-foreground truncate max-w-[200px]">
                        {result.primary_institution_name || '未知机构'}
                      </div>
                    </div>
                    <span className="text-xs bg-secondary px-2 py-1 rounded text-secondary-foreground">
                      {result.works_count} 篇
                    </span>
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-6 min-h-0">
        {/* Main Graph Area */}
        <div className="lg:col-span-3 flex flex-col bg-card rounded-xl border border-border shadow-sm overflow-hidden relative">
           {loading ? (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10 backdrop-blur-sm">
              <div className="text-center">
                <Loader2 className="h-12 w-12 animate-spin text-primary mb-4 mx-auto" />
                <p className="text-muted-foreground font-medium">正在构建引力场网络...</p>
              </div>
            </div>
          ) : nodes.length > 0 ? (
            <div className="flex-1 relative">
              <NetworkGraph
                nodes={nodes}
                edges={edges}
                centerNodeId={authorId}
                onNodeClick={handleNodeClick}
              />

              {/* Overlay Info */}
              <div className="absolute top-4 left-4 bg-background/90 backdrop-blur border border-border p-3 rounded-lg shadow-lg max-w-xs">
                 <div className="text-sm font-semibold text-foreground flex items-center gap-2 mb-1">
                   <User size={14} className="text-primary" />
                   {author?.display_name}
                 </div>
                 <div className="text-xs text-muted-foreground">
                   显示 Top {nodes.length - 1} 合作者
                 </div>
              </div>

              {/* Legend */}
              <div className="absolute bottom-4 right-4 bg-background/90 backdrop-blur border border-border p-3 rounded-lg shadow-lg text-xs space-y-2">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-blue-500"></span>
                  <span>中心节点</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-blue-200 border border-blue-400"></span>
                  <span>合作者 (大小代表频次)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-6 h-0.5 bg-gray-400"></span>
                  <span>合作关系 (粗细代表强度)</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8">
              <div className="w-20 h-20 bg-secondary/50 rounded-full flex items-center justify-center mb-6">
                <Network className="h-10 w-10 opacity-40" />
              </div>
              <h3 className="text-lg font-medium text-foreground mb-2">准备就绪</h3>
              <p className="max-w-sm text-center">
                请在右上角搜索框输入作者姓名，系统将为您生成可视化的学术合作网络图谱。
              </p>
            </div>
          )}
        </div>

        {/* Sidebar Info */}
        <div className="lg:col-span-1 flex flex-col gap-4 overflow-hidden">
          {collaborators.length > 0 ? (
            <div className="bg-card rounded-xl border border-border shadow-sm flex flex-col h-full overflow-hidden">
              <div className="p-4 border-b border-border bg-muted/30">
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <Users size={16} />
                  合作列表
                </h3>
              </div>
              <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin">
                {collaborators.slice(0, 50).map((collab, index) => (
                  <button
                    key={collab.id}
                    onClick={() => selectAuthor(collab.id)}
                    className="w-full text-left px-3 py-2 rounded-lg hover:bg-accent/50 text-sm flex items-center justify-between group transition-colors"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <span className="text-xs font-mono text-muted-foreground w-4">{index + 1}</span>
                      <span className="font-medium truncate text-foreground group-hover:text-primary transition-colors">
                        {collab.display_name}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground bg-secondary/50 px-1.5 py-0.5 rounded">
                      {collab.collaboration_count}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="bg-card rounded-xl border border-border shadow-sm p-6 text-center h-full flex flex-col items-center justify-center text-muted-foreground">
               <Info size={32} className="mb-3 opacity-20" />
               <p className="text-sm">暂无合作者列表</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default NetworkPage;
