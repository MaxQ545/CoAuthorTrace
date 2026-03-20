import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuthor } from '../hooks/queries';
import { useNetworkStream } from '../hooks/useNetworkStream';
import NetworkGraph from '../components/NetworkGraph';
import AuthorSelector from '../components/AuthorSelector';
import NetworkProgress from '../components/NetworkProgress';
import { useTimeFilter } from '../contexts/TimeFilterContext';
import { exportToCSV } from '../utils/export';
import {
  Network, Users, Play, RotateCcw, Settings2,
  ChevronDown, ChevronUp, Info, Waypoints, AlertTriangle, Download,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

function NetworkPage() {
  const { authorId } = useParams();
  const navigate = useNavigate();
  const { timeRange } = useTimeFilter();

  useEffect(() => {
    document.title = '合作网络 - CoAuthorTrace';
    return () => { document.title = '论文合作者追踪系统'; };
  }, []);

  // Seed authors selected by the user
  const [seedAuthors, setSeedAuthors] = useState([]);

  // Expansion parameters
  const [maxDepth, setMaxDepth] = useState(3);
  const [topK, setTopK] = useState(20);
  const [maxNodes, setMaxNodes] = useState(500);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Graph data accumulated from SSE
  const nodesMapRef = useRef(new Map());
  const edgesListRef = useRef([]);
  const edgeKeysRef = useRef(new Set());
  const [nodesCount, setNodesCount] = useState(0);
  const [edgesCount, setEdgesCount] = useState(0);

  // Component tracking
  const [components, setComponents] = useState(0);
  const [allConnected, setAllConnected] = useState(false);

  // Sidebar
  const [sidebarNodes, setSidebarNodes] = useState([]);

  // Graph ref for progressive updates
  const graphRef = useRef(null);

  // Batched update refs
  const pendingNodesRef = useRef([]);
  const pendingEdgesRef = useRef([]);
  const flushTimerRef = useRef(null);
  const sidebarTimerRef = useRef(null);
  const sidebarDirtyRef = useRef(false);

  // SSE hook
  const { state: streamState, progress, error: streamError, connect, disconnect } = useNetworkStream();

  // Legacy single-author support: auto-add URL param author as seed
  const { data: urlAuthor } = useAuthor(authorId);

  useEffect(() => {
    if (urlAuthor && authorId && seedAuthors.length === 0) {
      setSeedAuthors([{
        id: urlAuthor.id,
        display_name: urlAuthor.display_name,
        institution: urlAuthor.primary_institution_name || urlAuthor.last_known_institution_name || null,
        works_count: urlAuthor.works_count,
      }]);
    }
  }, [urlAuthor, authorId]);

  // Debounced sidebar sync (runs at most every 500ms)
  const scheduleSidebarSync = useCallback(() => {
    sidebarDirtyRef.current = true;
    if (!sidebarTimerRef.current) {
      sidebarTimerRef.current = setTimeout(() => {
        sidebarTimerRef.current = null;
        if (sidebarDirtyRef.current) {
          sidebarDirtyRef.current = false;
          setSidebarNodes([...nodesMapRef.current.values()]);
        }
      }, 500);
    }
  }, []);

  // Flush batched updates to vis-network and state
  const flushUpdates = useCallback(() => {
    if (pendingNodesRef.current.length > 0) {
      const nodes = pendingNodesRef.current;
      pendingNodesRef.current = [];
      for (const n of nodes) {
        nodesMapRef.current.set(n.id, n);
        graphRef.current?.addNode(n);
      }
      setNodesCount(nodesMapRef.current.size);
      scheduleSidebarSync();
    }
    if (pendingEdgesRef.current.length > 0) {
      const edges = pendingEdgesRef.current;
      pendingEdgesRef.current = [];
      for (const e of edges) {
        const key = [e.from, e.to].sort().join('-');
        if (!edgeKeysRef.current.has(key)) {
          edgeKeysRef.current.add(key);
          edgesListRef.current.push(e);
          graphRef.current?.addEdge(e);
        }
      }
      setEdgesCount(edgesListRef.current.length);
    }
    flushTimerRef.current = null;
  }, [scheduleSidebarSync]);

  const scheduleFlush = useCallback(() => {
    if (!flushTimerRef.current) {
      flushTimerRef.current = setTimeout(flushUpdates, 100);
    }
  }, [flushUpdates]);

  // Start the network build
  const handleBuild = useCallback(() => {
    if (seedAuthors.length === 0) return;

    // Reset graph data
    nodesMapRef.current = new Map();
    edgesListRef.current = [];
    edgeKeysRef.current = new Set();
    setNodesCount(0);
    setEdgesCount(0);
    setComponents(seedAuthors.length);
    setAllConnected(seedAuthors.length <= 1);
    setSidebarNodes([]);

    // Clear vis-network
    graphRef.current?.clear();

    const authorIds = seedAuthors.map(a => a.id);

    connect(
      {
        authorIds,
        maxDepth,
        topK,
        maxNodes,
        fromYear: timeRange.fromYear,
        toYear: timeRange.toYear,
      },
      {
        onNode: (data) => {
          pendingNodesRef.current.push(data);
          scheduleFlush();
        },
        onEdge: (data) => {
          pendingEdgesRef.current.push(data);
          scheduleFlush();
        },
        onProgress: (data) => {
          if (data.components != null) setComponents(data.components);
          if (data.all_connected != null) setAllConnected(data.all_connected);
        },
        onConnected: (data) => {
          setAllConnected(true);
          if (data.components != null) setComponents(data.components);
        },
        onComplete: (data) => {
          // Final flush (including sidebar)
          flushUpdates();
          if (sidebarTimerRef.current) {
            clearTimeout(sidebarTimerRef.current);
            sidebarTimerRef.current = null;
          }
          setSidebarNodes([...nodesMapRef.current.values()]);
          if (data.components != null) setComponents(data.components);
          if (data.all_connected != null) setAllConnected(data.all_connected);
          // Stabilize and fit after completion
          setTimeout(() => {
            graphRef.current?.stabilize();
            setTimeout(() => graphRef.current?.fit(), 500);
          }, 200);
        },
        onError: () => {
          // Flush whatever we have
          flushUpdates();
        },
      }
    );
  }, [seedAuthors, maxDepth, topK, maxNodes, timeRange, connect, scheduleFlush, flushUpdates]);

  // Reset everything
  const handleReset = useCallback(() => {
    disconnect();
    nodesMapRef.current = new Map();
    edgesListRef.current = [];
    edgeKeysRef.current = new Set();
    setNodesCount(0);
    setEdgesCount(0);
    setComponents(0);
    setAllConnected(false);
    setSidebarNodes([]);
    graphRef.current?.clear();
  }, [disconnect]);

  const handleAddAuthor = useCallback((author) => {
    setSeedAuthors(prev => {
      if (prev.some(a => a.id === author.id)) return prev;
      return [...prev, author];
    });
  }, []);

  const handleRemoveAuthor = useCallback((authorId) => {
    setSeedAuthors(prev => prev.filter(a => a.id !== authorId));
  }, []);

  const handleNodeClick = (nodeId) => {
    navigate(`/author/${nodeId}`);
  };

  const isStreaming = streamState === 'connecting' || streamState === 'streaming';
  const hasResults = nodesCount > 0;
  const canBuild = seedAuthors.length >= 1 && !isStreaming;

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (flushTimerRef.current) clearTimeout(flushTimerRef.current);
      if (sidebarTimerRef.current) clearTimeout(sidebarTimerRef.current);
    };
  }, []);

  return (
    <div className="space-y-4 animate-fade-in h-[calc(100vh-140px)] flex flex-col">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Network className="text-primary" />
            合作网络可视化
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            选择多位作者，渐进式展开学术合作网络
          </p>
        </div>
      </div>

      {/* Author Selection + Controls */}
      <div className="bg-card rounded-xl border border-border shadow-sm p-4 space-y-3">
        <div className="flex flex-col lg:flex-row gap-3">
          {/* Author selector */}
          <div className="flex-1">
            <AuthorSelector
              selectedAuthors={seedAuthors}
              onAdd={handleAddAuthor}
              onRemove={handleRemoveAuthor}
              maxAuthors={5}
              disabled={isStreaming}
            />
          </div>

          {/* Action buttons */}
          <div className="flex items-start gap-2 shrink-0">
            <button
              onClick={handleBuild}
              disabled={!canBuild}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed transition-colors font-medium text-sm"
            >
              <Play size={14} />
              {isStreaming ? '构建中...' : '构建网络'}
            </button>

            {hasResults && (
              <>
                <button
                  onClick={handleReset}
                  disabled={isStreaming}
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-secondary text-secondary-foreground rounded-xl hover:bg-secondary/80 disabled:opacity-50 transition-colors text-sm"
                >
                  <RotateCcw size={14} />
                  重置
                </button>
                <button
                  onClick={() => {
                    const data = [...nodesMapRef.current.values()].map(n => ({
                      id: n.id,
                      name: n.label || n.display_name || '',
                      institution: n.institution || '',
                      depth: n.depth ?? '',
                      works_count: n.works_count ?? '',
                    }));
                    exportToCSV(data, 'network_nodes.csv');
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-2.5 bg-secondary text-secondary-foreground rounded-xl hover:bg-secondary/80 transition-colors text-sm"
                  title="导出节点 (CSV)"
                >
                  <Download size={14} /> 节点
                </button>
                <button
                  onClick={() => {
                    const data = edgesListRef.current.map(e => ({
                      from: e.from,
                      to: e.to,
                      weight: e.value ?? e.weight ?? '',
                    }));
                    exportToCSV(data, 'network_edges.csv');
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-2.5 bg-secondary text-secondary-foreground rounded-xl hover:bg-secondary/80 transition-colors text-sm"
                  title="导出边 (CSV)"
                >
                  <Download size={14} /> 边
                </button>
              </>
            )}

            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="inline-flex items-center gap-1 px-3 py-2.5 text-muted-foreground hover:text-foreground hover:bg-secondary/50 rounded-xl transition-colors text-sm"
            >
              <Settings2 size={14} />
              {showAdvanced ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          </div>
        </div>

        {/* Advanced settings */}
        <AnimatePresence>
          {showAdvanced && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-3 border-t border-border">
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                    展开深度 (depth: {maxDepth})
                  </label>
                  <input
                    type="range"
                    min={1}
                    max={5}
                    value={maxDepth}
                    onChange={(e) => setMaxDepth(Number(e.target.value))}
                    disabled={isStreaming}
                    className="w-full accent-primary"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                    <span>1</span>
                    <span>2</span>
                    <span>3 (推荐)</span>
                    <span>4</span>
                    <span>5</span>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                    每节点展开数 (top-K: {topK})
                  </label>
                  <input
                    type="range"
                    min={5}
                    max={50}
                    step={5}
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                    disabled={isStreaming}
                    className="w-full accent-primary"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                    <span>5</span>
                    <span>20 (推荐)</span>
                    <span>50</span>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                    最大节点数 (max: {maxNodes})
                  </label>
                  <input
                    type="range"
                    min={100}
                    max={2000}
                    step={100}
                    value={maxNodes}
                    onChange={(e) => setMaxNodes(Number(e.target.value))}
                    disabled={isStreaming}
                    className="w-full accent-primary"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                    <span>100</span>
                    <span>500 (推荐)</span>
                    <span>2000</span>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Parameter combination warning */}
        {(maxDepth * topK > 100 || maxNodes > 1000) && (
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 text-xs pt-2 border-t border-border">
            <AlertTriangle size={14} className="shrink-0" />
            <span>当前参数组合可能导致加载时间较长 (Current parameters may cause long loading times)</span>
          </div>
        )}
      </div>

      {/* Progress */}
      {streamState !== 'idle' && (
        <NetworkProgress
          status={streamState === 'streaming' ? 'expanding' : streamState}
          progress={progress?.authors_total > 0 ? Math.round((progress.authors_processed / progress.authors_total) * 100) : 0}
          nodesCount={nodesCount}
          edgesCount={edgesCount}
          depth={progress?.depth ?? 0}
          components={components}
          allConnected={allConnected}
          seedCount={seedAuthors.length}
          error={streamError}
          onStop={disconnect}
        />
      )}

      {/* Main content area */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-4 min-h-0">
        {/* Graph */}
        <div className="lg:col-span-3 flex flex-col bg-card rounded-xl border border-border shadow-sm overflow-hidden relative">
          {/* Always mount NetworkGraph so vis-network initializes before streaming */}
          <div className={`flex-1 relative ${hasResults || isStreaming ? '' : 'invisible'}`}>
            <NetworkGraph
              ref={graphRef}
              nodes={[]}
              edges={[]}
              progressive={true}
              seedIds={seedAuthors.map(a => a.id)}
              onNodeClick={handleNodeClick}
            />

            {/* Overlay info */}
            {seedAuthors.length > 0 && hasResults && (
              <div className="absolute top-4 left-4 bg-background/90 backdrop-blur border border-border p-3 rounded-lg shadow-lg max-w-xs">
                <div className="text-sm font-semibold text-foreground flex items-center gap-2 mb-1">
                  <Waypoints size={14} className="text-primary" />
                  多作者网络
                </div>
                <div className="text-xs text-muted-foreground">
                  {seedAuthors.map(a => a.display_name).join(', ')}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {nodesCount} 节点 · {edgesCount} 连边
                </div>
              </div>
            )}

            {/* Legend */}
            {hasResults && (
              <div className="absolute bottom-4 right-4 bg-background/90 backdrop-blur border border-border p-3 rounded-lg shadow-lg text-xs space-y-1.5">
                <div className="font-medium text-foreground mb-1">图例</div>
                {DEPTH_LEGEND.map((item) => (
                  <div key={item.label} className="flex items-center gap-2">
                    <span
                      className="w-3 h-3 rounded-full border"
                      style={{ backgroundColor: item.bg, borderColor: item.border }}
                    />
                    <span className="text-muted-foreground">{item.label}</span>
                  </div>
                ))}
                <div className="flex items-center gap-2 pt-1 border-t border-border">
                  <span className="w-6 h-0.5 bg-gray-400" />
                  <span className="text-muted-foreground">合作关系</span>
                </div>
              </div>
            )}
          </div>

          {/* Empty state overlay — shown on top of the invisible graph */}
          {!hasResults && !isStreaming && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground p-8 bg-card">
              <div className="w-20 h-20 bg-secondary/50 rounded-full flex items-center justify-center mb-6">
                <Network className="h-10 w-10 opacity-40" />
              </div>
              <h3 className="text-lg font-medium text-foreground mb-2">准备就绪</h3>
              <p className="max-w-sm text-center text-sm">
                在上方搜索并选择作者，然后点击"构建网络"，系统将渐进式展开合作关系图谱。
              </p>
              <div className="mt-6 grid grid-cols-3 gap-4 text-center">
                <div className="space-y-1">
                  <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center mx-auto">
                    <Users size={16} className="text-primary" />
                  </div>
                  <div className="text-xs">选择作者</div>
                </div>
                <div className="space-y-1">
                  <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center mx-auto">
                    <Play size={16} className="text-primary" />
                  </div>
                  <div className="text-xs">构建网络</div>
                </div>
                <div className="space-y-1">
                  <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center mx-auto">
                    <Network size={16} className="text-primary" />
                  </div>
                  <div className="text-xs">探索关系</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1 flex flex-col gap-4 overflow-hidden">
          {sidebarNodes.length > 0 ? (
            <div className="bg-card rounded-xl border border-border shadow-sm flex flex-col h-full overflow-hidden">
              <div className="p-4 border-b border-border bg-muted/30">
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <Users size={16} />
                  网络节点 ({nodesCount})
                </h3>
              </div>
              <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin">
                {sidebarNodes
                  .sort((a, b) => (a.depth ?? 0) - (b.depth ?? 0) || (b.works_count || 0) - (a.works_count || 0))
                  .map((node, index) => {
                    const isSeed = node.is_seed || seedAuthors.some(s => s.id === node.id);
                    return (
                      <button
                        key={node.id}
                        onClick={() => navigate(`/author/${node.id}`)}
                        className="w-full text-left px-3 py-2 rounded-lg hover:bg-accent/50 text-sm flex items-center justify-between group transition-colors"
                      >
                        <div className="flex items-center gap-2 overflow-hidden">
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{
                              backgroundColor: isSeed
                                ? DEPTH_COLORS[0].background
                                : (DEPTH_COLORS[node.depth] || DEFAULT_NODE_COLOR).background,
                            }}
                          />
                          <span className="font-medium truncate text-foreground group-hover:text-primary transition-colors">
                            {node.label || node.display_name}
                          </span>
                        </div>
                        {isSeed && (
                          <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded font-medium shrink-0">
                            种子
                          </span>
                        )}
                      </button>
                    );
                  })}
              </div>
            </div>
          ) : (
            <div className="bg-card rounded-xl border border-border shadow-sm p-6 text-center h-full flex flex-col items-center justify-center text-muted-foreground">
              <Info size={32} className="mb-3 opacity-20" />
              <p className="text-sm">构建网络后将在此显示节点列表</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Depth legend data
const DEPTH_COLORS = [
  { background: '#2563EB', border: '#1E40AF' },
  { background: '#8B5CF6', border: '#6D28D9' },
  { background: '#EC4899', border: '#BE185D' },
  { background: '#F97316', border: '#C2410C' },
];

const DEFAULT_NODE_COLOR = { background: '#DBEAFE', border: '#3B82F6' };

const DEPTH_LEGEND = [
  { label: '种子作者 (深度 0)', bg: '#2563EB', border: '#1E40AF' },
  { label: '一级合作者 (深度 1)', bg: '#8B5CF6', border: '#6D28D9' },
  { label: '二级合作者 (深度 2)', bg: '#EC4899', border: '#BE185D' },
  { label: '三级合作者 (深度 3)', bg: '#F97316', border: '#C2410C' },
];

export default NetworkPage;
