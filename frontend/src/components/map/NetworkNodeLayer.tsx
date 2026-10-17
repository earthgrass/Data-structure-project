// Phase 5.1 —— 物流网络节点层（仓库 / 客户 / 中转）。
// 颜色 + 形状双重区分（dataviz：身份不能仅靠颜色）。
// 支持 hover 高亮 + 时间轴选中高亮（橙色更亮的描边）。

import type { NodeData } from '../../types';

interface PositionedNode {
  id: string;
  x: number;
  y: number;
}

interface NetworkNodeLayerProps {
  nodes: NodeData[];
  positions: Map<string, PositionedNode>;
  /** 当前路线涉及的节点（高亮环） */
  activeNodeIds: Set<string>;
  /** 鼠标 hover 节点（更亮高亮环） */
  hoverNodeId: string | null;
  /** 时间轴选中节点（最强描边） */
  timelineHighlightId?: string | null;
  onHover: (nodeId: string | null) => void;
}

const NODE_COLORS: Record<string, string> = {
  warehouse: 'var(--identity-warehouse)',
  transfer: 'var(--identity-transfer)',
  customer: 'var(--identity-customer)',
};

/** 节点形状：仓库=方形 / 中转=三角形 / 客户=圆形。 */
function NodeShape({
  type,
  x,
  y,
  fill,
}: {
  type: string;
  x: number;
  y: number;
  fill: string;
}) {
  if (type === 'warehouse') {
    return (
      <rect
        x={x - 6}
        y={y - 6}
        width={12}
        height={12}
        fill={fill}
        stroke="#ffffff"
        strokeWidth={1.5}
      />
    );
  }
  if (type === 'transfer') {
    const points = `${x},${y - 7} ${x + 7},${y + 5} ${x - 7},${y + 5}`;
    return (
      <polygon
        points={points}
        fill={fill}
        stroke="#ffffff"
        strokeWidth={1.5}
      />
    );
  }
  // customer
  return (
    <circle
      cx={x}
      cy={y}
      r={6}
      fill={fill}
      stroke="#ffffff"
      strokeWidth={1.5}
    />
  );
}

export function NetworkNodeLayer({
  nodes,
  positions,
  activeNodeIds,
  hoverNodeId,
  timelineHighlightId = null,
  onHover,
}: NetworkNodeLayerProps) {
  return (
    <g aria-label="物流网络节点">
      {nodes.map((n) => {
        const p = positions.get(n.id);
        if (!p) return null;
        const fill = NODE_COLORS[n.type] ?? 'var(--text-primary)';
        const onRoute = activeNodeIds.has(n.id);
        const isHover = hoverNodeId === n.id;
        const isTimeline = timelineHighlightId === n.id;
        return (
          <g
            key={`node-${n.id}`}
            onMouseEnter={() => onHover(n.id)}
            onMouseLeave={() => onHover(null)}
            style={{ cursor: 'pointer' }}
          >
            {/* 当前路线高亮（淡） */}
            {onRoute && (
              <circle
                cx={p.x}
                cy={p.y}
                r={10}
                fill="none"
                stroke="var(--status-serious)"
                strokeWidth={2}
                strokeOpacity={0.5}
              />
            )}
            {/* 时间轴选中（最强） */}
            {isTimeline && (
              <circle
                cx={p.x}
                cy={p.y}
                r={13}
                fill="var(--status-serious-soft)"
                stroke="var(--status-serious)"
                strokeWidth={2.5}
                fillOpacity={0.45}
              />
            )}
            {/* hover（次强） */}
            {isHover && (
              <circle
                cx={p.x}
                cy={p.y}
                r={11}
                fill="none"
                stroke="var(--text-primary)"
                strokeWidth={1.5}
              />
            )}
            <NodeShape type={n.type} x={p.x} y={p.y} fill={fill} />
            <text
              x={p.x}
              y={p.y + 18}
              textAnchor="middle"
              fontSize={10}
              fontWeight={isHover || onRoute || isTimeline ? 700 : 500}
              fill="var(--text-primary)"
              pointerEvents="none"
              style={{
                paintOrder: 'stroke',
                stroke: '#ffffff',
                strokeWidth: 3,
                strokeLinejoin: 'round',
              }}
            >
              {n.id}
            </text>
          </g>
        );
      })}
    </g>
  );
}
