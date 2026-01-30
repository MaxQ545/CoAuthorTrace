import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

function NetworkGraph({ nodes, edges, centerNodeId, onNodeClick }) {
  const containerRef = useRef(null);
  const networkRef = useRef(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return;

    const loadVisNetwork = async () => {
      setLoading(true);

      // Dynamic import vis-network
      const { Network } = await import('vis-network/standalone');
      const { DataSet } = await import('vis-data/standalone');

      // Prepare nodes with styling
      const visNodes = new DataSet(
        nodes.map((node) => ({
          id: node.id,
          label: node.label,
          title: `${node.label}\n论文: ${node.papers || 0}\n引用: ${node.citations || 0}`,
          color: node.id === centerNodeId
            ? { background: '#3B82F6', border: '#1D4ED8' }
            : { background: '#93C5FD', border: '#3B82F6' },
          size: node.id === centerNodeId ? 30 : Math.max(15, Math.min(25, 10 + (node.collabCount || 0))),
          font: {
            size: node.id === centerNodeId ? 14 : 12,
            color: '#1F2937',
          },
        }))
      );

      // Prepare edges with styling
      const visEdges = new DataSet(
        edges.map((edge, idx) => ({
          id: idx,
          from: edge.from,
          to: edge.to,
          value: edge.weight || 1,
          title: `合作次数: ${edge.count || 1}`,
          color: { color: '#CBD5E1', highlight: '#3B82F6' },
        }))
      );

      const options = {
        nodes: {
          shape: 'dot',
          borderWidth: 2,
          shadow: true,
        },
        edges: {
          width: 1,
          smooth: {
            type: 'continuous',
          },
          scaling: {
            min: 1,
            max: 5,
          },
        },
        physics: {
          enabled: true,
          solver: 'forceAtlas2Based',
          forceAtlas2Based: {
            gravitationalConstant: -50,
            centralGravity: 0.01,
            springLength: 100,
            springConstant: 0.08,
          },
          stabilization: {
            iterations: 100,
          },
        },
        interaction: {
          hover: true,
          tooltipDelay: 200,
          zoomView: true,
          dragView: true,
        },
      };

      // Destroy existing network
      if (networkRef.current) {
        networkRef.current.destroy();
      }

      // Create new network
      networkRef.current = new Network(
        containerRef.current,
        { nodes: visNodes, edges: visEdges },
        options
      );

      // Event handlers
      networkRef.current.on('click', (params) => {
        if (params.nodes.length > 0 && onNodeClick) {
          onNodeClick(params.nodes[0]);
        }
      });

      networkRef.current.on('stabilizationIterationsDone', () => {
        setLoading(false);
      });

      // Fallback for quick stabilization
      setTimeout(() => setLoading(false), 2000);
    };

    loadVisNetwork();

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
      }
    };
  }, [nodes, edges, centerNodeId]);

  return (
    <div className="relative">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-75 z-10">
          <div className="text-center">
            <div className="animate-spin text-4xl mb-2">⏳</div>
            <p className="text-gray-600">正在生成网络图...</p>
          </div>
        </div>
      )}
      <div
        ref={containerRef}
        className="w-full h-[500px] border border-gray-200 rounded-lg bg-white"
      />
      <div className="mt-2 text-sm text-gray-500 text-center">
        点击节点查看作者详情 · 滚轮缩放 · 拖拽移动
      </div>
    </div>
  );
}

export default NetworkGraph;
