import { useEffect, useRef, useState } from 'react';

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

      // Colors from our Tailwind theme
      // Primary: #2563EB (blue-600)
      // Secondary: #EFF6FF (blue-50)
      // Node Colors
      const centerColor = { background: '#2563EB', border: '#1E40AF' };
      const nodeColor = { background: '#DBEAFE', border: '#3B82F6' };
      const highlightColor = { background: '#93C5FD', border: '#1D4ED8' };

      // Prepare nodes with styling
      const visNodes = new DataSet(
        nodes.map((node) => ({
          id: node.id,
          label: node.label,
          title: `<div style="padding:4px; font-family: sans-serif;">
            <strong>${node.label}</strong><br/>
            论文: ${node.papers || 0}<br/>
            引用: ${node.citations || 0}
          </div>`,
          color: node.id === centerNodeId ? centerColor : nodeColor,
          size: node.id === centerNodeId ? 35 : Math.max(15, Math.min(30, 15 + (node.collabCount || 0) * 0.5)),
          font: {
            size: node.id === centerNodeId ? 16 : 14,
            face: 'Inter, system-ui, sans-serif',
            color: '#1F2937',
            strokeWidth: 4, // White outline for text
            strokeColor: '#ffffff',
          },
          borderWidth: 2,
          shadow: {
            enabled: true,
            color: 'rgba(0,0,0,0.1)',
            size: 10,
            x: 5,
            y: 5
          }
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
          color: { color: '#E2E8F0', highlight: '#3B82F6', opacity: 0.8 },
          width: Math.max(1, Math.min(5, (edge.count || 1) * 0.5)),
        }))
      );

      const options = {
        nodes: {
          shape: 'dot',
          scaling: {
            min: 10,
            max: 40,
            label: {
              enabled: true,
              min: 12,
              max: 20,
            },
          },
        },
        edges: {
          smooth: {
            type: 'continuous',
            forceDirection: 'none',
            roundness: 0.5
          },
        },
        physics: {
          enabled: true,
          solver: 'forceAtlas2Based',
          forceAtlas2Based: {
            gravitationalConstant: -80,
            centralGravity: 0.005,
            springLength: 150,
            springConstant: 0.05,
            damping: 0.4,
            avoidOverlap: 0.5
          },
          stabilization: {
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
          improvedLayout: true,
        }
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
    <div className="relative w-full h-full min-h-[500px] bg-slate-50/50">
      <div
        ref={containerRef}
        className="w-full h-full absolute inset-0 outline-none"
      />
    </div>
  );
}

export default NetworkGraph;
