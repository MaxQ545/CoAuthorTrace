import { useEffect, useRef, useState, forwardRef, useImperativeHandle, useCallback } from 'react';

// Depth-based color scheme for progressive mode
const DEPTH_COLORS = [
  { background: '#2563EB', border: '#1E40AF' },  // depth 0: seed (blue-600)
  { background: '#8B5CF6', border: '#6D28D9' },  // depth 1: purple-500
  { background: '#EC4899', border: '#BE185D' },  // depth 2: pink-500
  { background: '#F97316', border: '#C2410C' },  // depth 3: orange-500
];

const DEFAULT_NODE_COLOR = { background: '#DBEAFE', border: '#3B82F6' };
const CENTER_COLOR = { background: '#2563EB', border: '#1E40AF' };

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function createTooltip(html) {
  const el = document.createElement('div');
  el.innerHTML = html;
  return el;
}

function formatProgressiveNode(nodeData, seedIds = []) {
  const isSeed = nodeData.is_seed || seedIds.includes(nodeData.id);
  const depth = nodeData.depth ?? 0;
  const color = isSeed ? DEPTH_COLORS[0] : (DEPTH_COLORS[depth] || DEFAULT_NODE_COLOR);
  const name = nodeData.label || nodeData.display_name;

  return {
    id: nodeData.id,
    label: name,
    title: createTooltip(
      `<div style="padding:4px; font-family: sans-serif;">
        <strong>${escapeHtml(name)}</strong><br/>
        ${nodeData.institution ? `机构: ${escapeHtml(nodeData.institution)}<br/>` : ''}
        论文: ${parseInt(nodeData.works_count, 10) || 0}<br/>
        引用: ${parseInt(nodeData.cited_by_count, 10) || 0}
      </div>`
    ),
    color,
    size: isSeed ? 35 : Math.max(15, Math.min(30, 15 + (nodeData.works_count || 0) * 0.01)),
    font: {
      size: isSeed ? 16 : 13,
      face: 'Inter, system-ui, sans-serif',
      color: '#1F2937',
      strokeWidth: 4,
      strokeColor: '#ffffff',
    },
    borderWidth: isSeed ? 3 : 2,
    shadow: {
      enabled: true,
      color: 'rgba(0,0,0,0.1)',
      size: 10,
      x: 5,
      y: 5,
    },
  };
}

function formatProgressiveEdge(edgeData) {
  const count = edgeData.collaboration_count || edgeData.weight || 1;
  return {
    id: [edgeData.from, edgeData.to].sort().join('-'),
    from: edgeData.from,
    to: edgeData.to,
    value: edgeData.weight || count,
    title: createTooltip(`合作次数: ${count}`),
    color: { color: '#E2E8F0', highlight: '#3B82F6', opacity: 0.8 },
    width: Math.max(1, Math.min(5, count * 0.5)),
  };
}

const NetworkGraph = forwardRef(function NetworkGraph(
  { nodes, edges, centerNodeId, onNodeClick, progressive = false, seedIds = [] },
  ref
) {
  const containerRef = useRef(null);
  const networkRef = useRef(null);
  const visNodesRef = useRef(null);
  const visEdgesRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const initRef = useRef(false);

  // Initialize vis-network (once for progressive mode, or on data change for legacy)
  const initNetwork = useCallback(async (initialNodes = [], initialEdges = []) => {
    if (!containerRef.current) return;

    setLoading(true);

    const { Network } = await import('vis-network/standalone');
    const { DataSet } = await import('vis-data/standalone');

    // Destroy existing network
    if (networkRef.current) {
      networkRef.current.destroy();
    }

    if (progressive) {
      // Progressive mode: start with empty DataSets
      visNodesRef.current = new DataSet();
      visEdgesRef.current = new DataSet();
    } else {
      // Legacy mode: populate DataSets from props
      visNodesRef.current = new DataSet(
        initialNodes.map((node) => ({
          id: node.id,
          label: node.label,
          title: createTooltip(
            `<div style="padding:4px; font-family: sans-serif;">
              <strong>${escapeHtml(node.label)}</strong><br/>
              论文: ${parseInt(node.papers, 10) || 0}<br/>
              引用: ${parseInt(node.citations, 10) || 0}
            </div>`
          ),
          color: node.id === centerNodeId ? CENTER_COLOR : DEFAULT_NODE_COLOR,
          size: node.id === centerNodeId ? 35 : Math.max(15, Math.min(30, 15 + (node.collabCount || 0) * 0.5)),
          font: {
            size: node.id === centerNodeId ? 16 : 14,
            face: 'Inter, system-ui, sans-serif',
            color: '#1F2937',
            strokeWidth: 4,
            strokeColor: '#ffffff',
          },
          borderWidth: 2,
          shadow: {
            enabled: true,
            color: 'rgba(0,0,0,0.1)',
            size: 10,
            x: 5,
            y: 5,
          },
        }))
      );

      visEdgesRef.current = new DataSet(
        initialEdges.map((edge, idx) => ({
          id: idx,
          from: edge.from,
          to: edge.to,
          value: edge.weight || 1,
          title: createTooltip(`合作次数: ${edge.count || 1}`),
          color: { color: '#E2E8F0', highlight: '#3B82F6', opacity: 0.8 },
          width: Math.max(1, Math.min(5, (edge.count || 1) * 0.5)),
        }))
      );
    }

    const options = {
      nodes: {
        shape: 'dot',
        scaling: {
          min: 10,
          max: 40,
          label: { enabled: true, min: 12, max: 20 },
        },
      },
      edges: {
        smooth: {
          type: 'continuous',
          forceDirection: 'none',
          roundness: 0.5,
        },
      },
      physics: {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: progressive
          ? {
              gravitationalConstant: -50,
              centralGravity: 0.005,
              springLength: 200,
              springConstant: 0.05,
              damping: 0.5,
              avoidOverlap: 0.5,
            }
          : {
              gravitationalConstant: -80,
              centralGravity: 0.005,
              springLength: 150,
              springConstant: 0.05,
              damping: 0.4,
              avoidOverlap: 0.5,
            },
        stabilization: progressive
          ? { enabled: false }
          : {
              enabled: true,
              iterations: 200,
              updateInterval: 25,
              onlyDynamicEdges: false,
              fit: true,
            },
      },
      interaction: {
        hover: true,
        tooltipDelay: 100,
        zoomView: true,
        dragView: true,
        navigationButtons: false,
        keyboard: false,
      },
      layout: {
        improvedLayout: !progressive,
      },
    };

    networkRef.current = new Network(
      containerRef.current,
      { nodes: visNodesRef.current, edges: visEdgesRef.current },
      options
    );

    networkRef.current.on('click', (params) => {
      if (params.nodes.length > 0 && onNodeClick) {
        onNodeClick(params.nodes[0]);
      }
    });

    if (!progressive) {
      networkRef.current.on('stabilizationIterationsDone', () => {
        setLoading(false);
      });
      setTimeout(() => setLoading(false), 2000);
    } else {
      setLoading(false);
    }

    initRef.current = true;
  }, [progressive, centerNodeId, onNodeClick]);

  // Legacy mode: reinit on data change
  useEffect(() => {
    if (progressive) return;
    if (nodes.length === 0) return;
    initNetwork(nodes, edges);

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, [nodes, edges, centerNodeId, progressive]);

  // Progressive mode: init once on mount
  useEffect(() => {
    if (!progressive) return;
    initNetwork();

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, [progressive]);

  // Imperative API for progressive mode
  useImperativeHandle(ref, () => ({
    addNode(nodeData) {
      if (!visNodesRef.current) return;
      try {
        const formatted = formatProgressiveNode(nodeData, seedIds);
        const existing = visNodesRef.current.get(nodeData.id);
        if (existing) {
          visNodesRef.current.update(formatted);
        } else {
          visNodesRef.current.add(formatted);
        }
      } catch (e) {
        // Silently handle duplicate add
      }
    },

    addEdge(edgeData) {
      if (!visEdgesRef.current) return;
      try {
        const formatted = formatProgressiveEdge(edgeData);
        const existing = visEdgesRef.current.get(formatted.id);
        if (!existing) {
          visEdgesRef.current.add(formatted);
        }
      } catch (e) {
        // Silently handle duplicate add
      }
    },

    fit() {
      if (networkRef.current) {
        networkRef.current.fit({
          animation: { duration: 500, easingFunction: 'easeInOutQuad' },
        });
      }
    },

    stabilize() {
      if (networkRef.current) {
        networkRef.current.stabilize(300);
      }
    },

    clear() {
      if (visNodesRef.current) visNodesRef.current.clear();
      if (visEdgesRef.current) visEdgesRef.current.clear();
    },

    getNodeCount() {
      return visNodesRef.current ? visNodesRef.current.length : 0;
    },

    getEdgeCount() {
      return visEdgesRef.current ? visEdgesRef.current.length : 0;
    },
  }), [seedIds]);

  return (
    <div className="relative w-full h-full min-h-[500px] bg-slate-50/50">
      <div
        ref={containerRef}
        className="w-full h-full absolute inset-0 outline-none"
      />
    </div>
  );
});

export default NetworkGraph;
