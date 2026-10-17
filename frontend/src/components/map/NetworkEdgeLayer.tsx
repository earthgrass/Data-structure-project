// Phase 5 —— 物流网络边层（非路线 / 路线高亮分层）。

interface PositionedNode {
  id: string;
  x: number;
  y: number;
}

interface EdgeLayerProps {
  positions: Map<string, PositionedNode>;
  edges: { source: string; target: string }[];
  /** 当前路线经过的边（高亮显示） */
  activeEdges: Set<string>;
}

/** 物流边：源 → 目标的有向箭头。
 * - 非路线边：淡灰（var(--identity-route-edge)），线宽 1.4
 * - 当前路线边：橙色（var(--identity-route-active)），线宽 3.0
 */
export function NetworkEdgeLayer({ positions, edges, activeEdges }: EdgeLayerProps) {
  return (
    <g aria-label="物流网络边">
      {edges.map((e, i) => {
        const src = positions.get(e.source);
        const tgt = positions.get(e.target);
        if (!src || !tgt) return null;
        const key = `${e.source}->${e.target}`;
        const active = activeEdges.has(key);
        return (
          <line
            key={`edge-${i}`}
            x1={src.x}
            y1={src.y}
            x2={tgt.x}
            y2={tgt.y}
            stroke={active ? 'var(--identity-route-active)' : 'var(--identity-route-edge)'}
            strokeWidth={active ? 3.0 : 1.4}
            strokeOpacity={active ? 1.0 : 0.55}
            markerEnd={active ? 'url(#arrow-route-active)' : 'url(#arrow-route-idle)'}
          />
        );
      })}
    </g>
  );
}