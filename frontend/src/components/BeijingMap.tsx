// Phase 5.2 —— NetworkMap 主视觉的 SVG 内核。
//
// 数据归属（受 FinAgent-X V2 工程实践启发）：
//   - OWN：渲染路网、节点、当前路线、图例位置
//   - NOT OWN：不调用任何 API；节点坐标 / 路线顺序全部来自 props
//   - DISPLAY：完全受控组件；props 变化即重渲染
//   - 严禁在本组件内 mock 数据；严禁凭空生成 POI 属性
//
// 渲染顺序（z-order）：
//   1. 行政区划底板（DistrictLayer）
//   2. 物流边（NetworkEdgeLayer，受 showNetworkEdges 控制）
//   3. 路线（当前 route 高亮，NetworkEdgeLayer 同层）
//   4. 节点（NetworkNodeLayer）
//   5. 节点标签
//   6. Tooltip / 交互覆盖层

import { useEffect, useMemo, useRef, useState } from 'react';
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
  /** 是否显示网络普通边（淡灰细线）；关闭时只显示当前路线 */
  showNetworkEdges?: boolean;
  /** 当前时间轴选中的节点（同步高亮） */
  activeTimelineNodeId?: string | null;
  /** 节点 hover 时通知父组件（用于在时间轴联动） */
  onNodeHover?: (nodeId: string | null) => void;
}

interface HoverInfo {
  node: NodeData;
  districtName: string | null;
  onRoute: boolean;
  sampleOrderCount: number;
}

const VIEW_W = 820;
const VIEW_H = 600;

export function BeijingMap({
  graph,
  route,
  showNetworkEdges = true,
  activeTimelineNodeId = null,
  onNodeHover,
}: BeijingMapProps) {
  const [hoverNodeId, setHoverNodeId] = useState<string | null>(null);
  const positionsRef = useRef<Map<string, { id: string; x: number; y: number }>>(
    new Map(),
  );
  const [positionsTick, setPositionsTick] = useState(0);

  // 投影 bbox 固定（按北京 16 区）
  const projection = useMemo(() => {
    const bbox = BEIJING_DISTRICTS.metadata.bbox;
    return makeProjection(
      { minLng: bbox[0], maxLng: bbox[2], minLat: bbox[1], maxLat: bbox[3] },
      VIEW_W, VIEW_H, 30, 30,
    );
  }, []);

  // 节点位置重算
  useEffect(() => {
    const map = new Map<string, { id: string; x: number; y: number }>();
    if (!graph) {
      positionsRef.current = map;
      setPositionsTick((t) => t + 1);
      return;
    }
    const fallbackBBox = computeNodeBBox(graph.nodes);
    for (const n of graph.nodes) {
      const p = projectNode(n, projection, fallbackBBox, VIEW_W, VIEW_H, 30, 30);
      map.set(n.id, { id: n.id, x: p.x, y: p.y });
    }
    positionsRef.current = map;
    setPositionsTick((t) => t + 1);
  }, [graph, projection]);

  const positions = positionsRef.current;

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

  function handleHover(nodeId: string | null) {
    setHoverNodeId(nodeId);
    onNodeHover?.(nodeId);
  }

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

  const highlightedNodeIds = new Set<string>(
    activeNodeIds,
  );
  if (activeTimelineNodeId) highlightedNodeIds.add(activeTimelineNodeId);

  const hoverPos = hoverNodeId ? positions.get(hoverNodeId) : null;

  return (
    <svg
      className="map-svg"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="北京区域物流网络图"
      key={positionsTick}
    >
      <defs>
        <marker
          id="arrow-route-idle"
          viewBox="0 0 10 10"
          refX={9}
          refY={5}
          markerWidth={5}
          markerHeight={5}
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="var(--identity-route-edge)" />
        </marker>
        <marker
          id="arrow-route-active"
          viewBox="0 0 10 10"
          refX={9}
          refY={5}
          markerWidth={6}
          markerHeight={6}
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="var(--identity-route-active)" />
        </marker>
      </defs>

      {/* 1. 行政区划底板 */}
      <DistrictLayer project={projection} />

      {/* 2. 物流边（开关控制） */}
      {showNetworkEdges && (
        <NetworkEdgeLayer
          positions={positions}
          edges={graph.edges as EdgeData[]}
          activeEdges={activeEdges}
        />
      )}

      {/* 3. 物流节点（顶层） */}
      <NetworkNodeLayer
        nodes={graph.nodes as NodeData[]}
        positions={positions}
        activeNodeIds={activeNodeIds}
        hoverNodeId={hoverNodeId}
        timelineHighlightId={activeTimelineNodeId}
        onHover={handleHover}
      />

      {/* 4. 节点悬停 tooltip（HTML overlay） */}
      {hoverInfo && hoverPos && (
        <foreignObject
          x={Math.min(hoverPos.x + 10, VIEW_W - 230)}
          y={Math.max(hoverPos.y - 60, 10)}
          width={220}
          height={80}
        >
          <div className="map-tooltip">
            <strong>{hoverInfo.node.name}</strong>
            <div className="meta">
              ID: {hoverInfo.node.id}
            </div>
            <div className="meta">
              类型：{hoverInfo.node.type} · 区域：{hoverInfo.districtName ?? '未知区'}
            </div>
            {hoverInfo.onRoute && (
              <span className="badge-on-route">当前路线经过</span>
            )}
          </div>
        </foreignObject>
      )}
    </svg>
  );
}
