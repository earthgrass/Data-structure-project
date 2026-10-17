// Phase 5 —— 北京区域 + 物流网络 + 配送路线渲染器。
// 渲染顺序：背景 → 行政区划 → 物流边 → 节点（节点必须在边之上）。

import { useMemo, useState } from 'react';
import type { EdgeData, GraphData, NodeData, RoutePlanData } from '../types';
import {
  BEIJING_DISTRICTS, findDistrict,
} from '../data/beijing-districts';
import {
  computeNodeBBox, makeProjection, projectNode,
} from './map/projection';
import { DistrictLayer } from './map/DistrictLayer';
import { NetworkEdgeLayer } from './map/NetworkEdgeLayer';
import { NetworkNodeLayer } from './map/NetworkNodeLayer';

interface BeijingMapProps {
  graph: GraphData | null;
  route: RoutePlanData | null;
}

interface HoverInfo {
  node: NodeData;
  districtName: string | null;
  onRoute: boolean;
  sampleOrderCount: number;
}

const VIEW_W = 820;
const VIEW_H = 600;

export function BeijingMap({ graph, route }: BeijingMapProps) {
  const [hoverNodeId, setHoverNodeId] = useState<string | null>(null);

  const projection = useMemo(() => {
    // 投影以北京 16 区 bbox 为基准；节点位置若在 bbox 外仍能落点
    const bbox = BEIJING_DISTRICTS.metadata.bbox;
    return makeProjection(
      { minLng: bbox[0], maxLng: bbox[2], minLat: bbox[1], maxLat: bbox[3] },
      VIEW_W, VIEW_H, 30, 30,
    );
  }, []);

  const positions = useMemo(() => {
    const map = new Map<string, { id: string; x: number; y: number }>();
    if (!graph) return map;
    const fallbackBBox = computeNodeBBox(graph.nodes);
    for (const n of graph.nodes) {
      const p = projectNode(n, projection, fallbackBBox, VIEW_W, VIEW_H, 30, 30);
      map.set(n.id, { id: n.id, x: p.x, y: p.y });
    }
    return map;
  }, [graph, projection]);

  const activeEdges = useMemo(() => {
    const set = new Set<string>();
    if (!route) return set;
    for (let i = 0; i < route.stop_sequence.length - 1; i++) {
      set.add(`${route.stop_sequence[i]}->${route.stop_sequence[i + 1]}`);
    }
    return set;
  }, [route]);

  const activeNodeIds = useMemo(() => {
    const set = new Set<string>();
    if (!route) return set;
    for (const id of route.stop_sequence) set.add(id);
    return set;
  }, [route]);

  const hoverInfo = useMemo<HoverInfo | null>(() => {
    if (!graph || !hoverNodeId) return null;
    const node = graph.nodes.find((n: NodeData) => n.id === hoverNodeId);
    if (!node) return null;
    const district = node.lng != null && node.lat != null
      ? findDistrict(node.lng, node.lat)
      : null;
    let sampleOrderCount = 0;
    if (route && route.stop_sequence.includes(hoverNodeId)) {
      sampleOrderCount = route.served_order_ids.length;
    }
    return {
      node,
      districtName: district?.name ?? null,
      onRoute: activeNodeIds.has(node.id),
      sampleOrderCount,
    };
  }, [graph, hoverNodeId, route, activeNodeIds]);

  if (!graph) {
    return (
      <div className="map-empty">
        <div>
          <strong>暂无场景</strong>
          <br />
          请在左侧 <em>场景控制</em> 中点击 <strong>随机生成场景</strong>。
        </div>
      </div>
    );
  }

  return (
    <svg
      className="map-svg"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="北京区域物流网络图"
    >
      <defs>
        <marker id="arrow-route-idle" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--identity-route-edge)" />
        </marker>
        <marker id="arrow-route-active" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--identity-route-active)" />
        </marker>
      </defs>

      {/* 1. 行政区划底板 */}
      <DistrictLayer project={projection} />

      {/* 2. 物流边 */}
      <NetworkEdgeLayer
        positions={positions}
        edges={graph.edges as EdgeData[]}
        activeEdges={activeEdges}
      />

      {/* 3. 物流节点（顶层） */}
      <NetworkNodeLayer
        nodes={graph.nodes as NodeData[]}
        positions={positions}
        activeNodeIds={activeNodeIds}
        hoverNodeId={hoverNodeId}
        onHover={setHoverNodeId}
      />

      {/* 4. 节点悬停 tooltip（HTML overlay） */}
      {hoverInfo && (
        <foreignObject x={positions.get(hoverInfo.node.id)!.x + 10}
                       y={positions.get(hoverInfo.node.id)!.y - 30}
                       width={180} height={70}>
          <div style={{
            background: 'white',
            border: '1px solid var(--border-strong)',
            borderRadius: 4,
            padding: '4px 8px',
            fontSize: 11,
            color: 'var(--text-primary)',
            boxShadow: 'var(--shadow-sm)',
            pointerEvents: 'none',
          }}>
            <div style={{ fontWeight: 700 }}>{hoverInfo.node.name}</div>
            <div style={{ color: 'var(--text-secondary)' }}>
              {hoverInfo.node.type} · {hoverInfo.districtName ?? '未知区'}
            </div>
            {hoverInfo.onRoute && (
              <div style={{ color: 'var(--status-serious)' }}>当前路线经过</div>
            )}
          </div>
        </foreignObject>
      )}
    </svg>
  );
}