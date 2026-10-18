// Phase 5 —— 物流网络边层（非路线 / 路线高亮分层）。

interface PositionedNode {
  id: string;
  x: number;
  y: number;
}

interface EdgeLayerProps {
  showNetworkEdges?: boolean;
  positions: Map<string, PositionedNode>;
  edges: { source: string; target: string }[];
  /** 当前路线经过的边（高亮显示） */
  activeEdges: Set<string>;
}

/** 物流边：源 → 目标的有向箭头。
 * - 非路线边：低对比度淡灰，线宽 0.85。
 * - 当前路线边：橙色（var(--identity-route-active)），线宽 3.0
 */
export function NetworkEdgeLayer({ positions, edges, activeEdges, showNetworkEdges = true }: EdgeLayerProps) {
  return (
    <g aria-label="物流网络边">
      {[false, true].map((activeLayer) => <g key={String(activeLayer)}>{edges.map((e, i) => {
        const src = positions.get(e.source);
        const tgt = positions.get(e.target);
        if (!src || !tgt) return null;
        const key = `${e.source}->${e.target}`;
        const active = activeEdges.has(key);
        if (active !== activeLayer || (!active && !showNetworkEdges)) return null;
        return (
          <line
            key={`edge-${i}`}
            x1={src.x}
            y1={src.y}
            x2={tgt.x}
            y2={tgt.y}
            stroke={active ? 'var(--identity-route-active)' : 'var(--identity-route-edge)'}
            strokeWidth={active ? 3.0 : 0.85}
            strokeOpacity={active ? 0.9 : 0.32}
            markerEnd={active ? 'url(#arrow-route-active)' : 'url(#arrow-route-idle)'}
          />
        );
      })}</g>)}
    </g>
  );
}
