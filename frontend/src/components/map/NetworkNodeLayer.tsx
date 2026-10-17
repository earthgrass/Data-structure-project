// Phase 5 —— 物流网络节点层（仓库 / 客户 / 中转）。
// 颜色 + 形状双重区分（dataviz：身份不能仅靠颜色）。

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
  /** 选中节点 ID（高亮环更亮） */
  hoverNodeId: string | null;
  onHover: (nodeId: string | null) => void;
}

const NODE_COLORS: Record<string, string> = {
  warehouse: 'var(--identity-warehouse)',
  transfer: 'var(--identity-transfer)',
  customer: 'var(--identity-customer)',
};

/** 节点形状：仓库=方形 / 中转=三角形 / 客户=圆形。
 * 颜色 + 形状双重区分，避免色盲场景。
 */
function NodeShape({ type, x, y, fill }: { type: string; x: number; y: number; fill: string }) {
  if (type === 'warehouse') {
    return (
      <rect
        x={x - 6} y={y - 6} width={12} height={12}
        fill={fill} stroke="#ffffff" strokeWidth={1.5}
      />
    );
  }
  if (type === 'transfer') {
    const points = `${x},${y - 7} ${x + 7},${y + 5} ${x - 7},${y + 5}`;
    return (
      <polygon
        points={points} fill={fill} stroke="#ffffff" strokeWidth={1.5}
      />
    );
  }
  // customer
  return <circle cx={x} cy={y} r={6} fill={fill} stroke="#ffffff" strokeWidth={1.5} />;
}

export function NetworkNodeLayer({
  nodes,
  positions,
  activeNodeIds,
  hoverNodeId,
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
        return (
          <g
            key={`node-${n.id}`}
            onMouseEnter={() => onHover(n.id)}
            onMouseLeave={() => onHover(null)}
            style={{ cursor: 'pointer' }}
          >
            {onRoute && (
              <circle
                cx={p.x} cy={p.y} r={10}
                fill="none"
                stroke="var(--status-serious)"
                strokeWidth={2}
                strokeOpacity={0.6}
              />
            )}
            {isHover && (
              <circle
                cx={p.x} cy={p.y} r={13}
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
              fontWeight={isHover || onRoute ? 700 : 500}
              fill="var(--text-primary)"
              pointerEvents="none"
            >
              {n.id}
            </text>
          </g>
        );
      })}
    </g>
  );
}