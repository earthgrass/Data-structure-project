// NetworkGraph —— SVG 有向图渲染器。
// 输入：节点 + 边 + 路线（可选）。输出：交互式 SVG。
// 设计：纯 SVG + React，无第三方绘图库（AGENTS §2.1 算法核心禁表；
// SVG 渲染属于通用 UI，不属于"算法"）。

import { useMemo } from 'react';
import type {
  EdgeData,
  GraphData,
  RoutePlanData,
} from '../types';

interface NetworkGraphProps {
  graph: GraphData | null;
  route: RoutePlanData | null;
  highlightOrderIds?: string[];
}

const NODE_COLORS = {
  warehouse: '#c2410c',
  transfer: '#6b7280',
  customer: '#1e40af',
} as const;

const VIEW_W = 800;
const VIEW_H = 600;
const PAD = 40;

export function NetworkGraph({ graph, route }: NetworkGraphProps) {
  const layout = useMemo(() => {
    if (!graph || graph.nodes.length === 0) return null;

    // 坐标归一化到 [PAD, VIEW_W - PAD] / [PAD, VIEW_H - PAD]
    const xs = graph.nodes.map((n) => n.x);
    const ys = graph.nodes.map((n) => n.y);
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    const yMin = Math.min(...ys);
    const yMax = Math.max(...ys);
    const xRange = xMax - xMin || 1;
    const yRange = yMax - yMin || 1;

    const positioned = new Map<string, { x: number; y: number; type: string }>();
    for (const n of graph.nodes) {
      const px = PAD + ((n.x - xMin) / xRange) * (VIEW_W - 2 * PAD);
      const py = PAD + (1 - (n.y - yMin) / yRange) * (VIEW_H - 2 * PAD);
      positioned.set(n.id, { x: px, y: py, type: n.type });
    }
    return positioned;
  }, [graph]);

  if (!graph || !layout) {
    return (
      <div className="network-empty">
        <div>
          <strong>暂无场景</strong>
          <br />
          请在左侧 <em>场景控制</em> 中点击 <strong>随机生成场景</strong>。
        </div>
      </div>
    );
  }

  // 路线集合
  const routeEdgeSet = new Set<string>();
  const routeNodeOrder: string[] = [];
  if (route) {
    for (let i = 0; i < route.stop_sequence.length - 1; i++) {
      const a = route.stop_sequence[i];
      const b = route.stop_sequence[i + 1];
      routeEdgeSet.add(`${a}->${b}`);
      routeNodeOrder.push(a);
    }
  }

  return (
    <svg
      className="network-graph"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="物流网络图"
    >
      <defs>
        <marker
          id="arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ca3af" />
        </marker>
        <marker
          id="arrow-route"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#c2410c" />
        </marker>
      </defs>

      {/* 边 */}
      {graph.edges.map((e: EdgeData, i) => {
        const src = layout.get(e.source);
        const tgt = layout.get(e.target);
        if (!src || !tgt) return null;
        const onRoute = routeEdgeSet.has(`${e.source}->${e.target}`);
        return (
          <line
            key={`edge-${i}`}
            x1={src.x}
            y1={src.y}
            x2={tgt.x}
            y2={tgt.y}
            stroke={onRoute ? '#c2410c' : '#9ca3af'}
            strokeWidth={onRoute ? 2.2 : 0.8}
            strokeOpacity={onRoute ? 1 : 0.45}
            markerEnd={onRoute ? 'url(#arrow-route)' : 'url(#arrow)'}
          />
        );
      })}

      {/* 节点 */}
      {graph.nodes.map((n) => {
        const p = layout.get(n.id);
        if (!p) return null;
        const onRoute = routeNodeOrder.includes(n.id);
        const color = NODE_COLORS[n.type as keyof typeof NODE_COLORS] ?? '#1a1d22';
        const radius = n.type === 'warehouse' ? 9 : n.type === 'transfer' ? 6 : 5;
        return (
          <g key={`node-${n.id}`}>
            <circle
              cx={p.x}
              cy={p.y}
              r={radius}
              fill={color}
              stroke={onRoute ? '#fbbf24' : '#ffffff'}
              strokeWidth={onRoute ? 2.5 : 1.5}
            />
            <text
              x={p.x}
              y={p.y - radius - 4}
              textAnchor="middle"
              fontSize={10}
              fill="#1a1d22"
              fontWeight={onRoute ? 700 : 500}
            >
              {n.id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}