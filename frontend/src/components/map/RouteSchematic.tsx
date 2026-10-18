// Phase 5.3 —— RouteSchematic：路线网络示意图（去行政区划）。
//
// 设计：
//   * v3 替代 v2 的 BeijingMap —— 不再叠加北京 16 区示意 GeoJSON；
//   * 节点坐标直接用 NodeData.x / NodeData.y（抽象 [0, 100] 坐标系）；
//   * 渲染顺序：物流边 → 当前路线边 → 节点 → 节点标签 → hover tooltip；
//   * 数据归属：完全受控；不调用任何 API；不引入 mock。
//
// 不变量：
//   * 所有 NodeData 必须有 finite 的 x / y；否则视为非法并显示空态。
//   * 当前路线高亮（activeEdges）由 route.road_node_sequence 派生；
//   * 节点 hover 同时通知 onNodeHover（与 RouteTimeline 联动）。

import { useEffect, useMemo, useRef, useState } from 'react';
import type { EdgeData, GraphData, NodeData, RoutePlanData } from '../../types';
import {
  computeNodeBBox, makeProjection, projectNode,
} from './projection';
import { NetworkEdgeLayer } from './NetworkEdgeLayer';
import { NetworkNodeLayer } from './NetworkNodeLayer';

export interface RouteSchematicProps {
  graph: GraphData | null;
  route: RoutePlanData | null;
  /** 是否显示网络普通边（淡灰细线）；关闭时只显示当前路线 */
  showNetworkEdges?: boolean;
  /** 当前时间轴选中的节点（同步高亮） */
  activeTimelineNodeId?: string | null;
  /** 节点 hover 时通知父组件（用于时间轴联动） */
  onNodeHover?: (nodeId: string | null) => void;
  /** 实时回放：当前 leg 的实际道路节点路径与进度 */
  vehiclePosition?: { path: string[]; t: number } | null;
  /** 实时回放：已完成的站点集合 */
  completedStops?: ReadonlySet<string>;
}

interface HoverInfo {
  node: NodeData;
  onRoute: boolean;
  servedOrderCount: number;
}

const VIEW_W = 820;
const VIEW_H = 600;

function positionOnRoadPath(
  path: string[],
  progress: number,
  positions: Map<string, { x: number; y: number }>,
  edgeTimes: Map<string, number>,
): { x: number; y: number } | null {
  if (path.length === 0) return null;
  if (path.length === 1) return positions.get(path[0]) ?? null;

  const segmentTimes: number[] = [];
  let totalTime = 0;
  for (let i = 0; i < path.length - 1; i++) {
    const from = positions.get(path[i]);
    const to = positions.get(path[i + 1]);
    const time = edgeTimes.get(`${path[i]}->${path[i + 1]}`);
    if (!from || !to || time === undefined) return null;
    const duration = Number.isFinite(time) && time > 0 ? time : 1;
    segmentTimes.push(duration);
    totalTime += duration;
  }

  let elapsed = Math.min(1, Math.max(0, progress)) * totalTime;
  for (let i = 0; i < segmentTimes.length; i++) {
    const duration = segmentTimes[i];
    if (elapsed <= duration || i === segmentTimes.length - 1) {
      const from = positions.get(path[i])!;
      const to = positions.get(path[i + 1])!;
      const t = Math.min(1, Math.max(0, elapsed / duration));
      return { x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t };
    }
    elapsed -= duration;
  }
  return null;
}

export function RouteSchematic({
  graph,
  route,
  showNetworkEdges = true,
  activeTimelineNodeId = null,
  onNodeHover,
  vehiclePosition = null,
  completedStops,
}: RouteSchematicProps) {
  const [hoverNodeId, setHoverNodeId] = useState<string | null>(null);
  const positionsRef = useRef<Map<string, { id: string; x: number; y: number }>>(
    new Map(),
  );
  const [positionsTick, setPositionsTick] = useState(0);

  // 投影 bbox 由场景节点的 x/y 派生
  const projection = useMemo(() => {
    if (!graph) return null;
    const bbox = computeNodeBBox(graph.nodes as NodeData[]);
    return makeProjection(bbox, VIEW_W, VIEW_H, 30, 30);
  }, [graph]);

  // 节点位置重算
  useEffect(() => {
    const map = new Map<string, { id: string; x: number; y: number }>();
    if (!graph || !projection) {
      positionsRef.current = map;
      setPositionsTick((t) => t + 1);
      return;
    }
    for (const n of graph.nodes as NodeData[]) {
      if (!Number.isFinite(n.x) || !Number.isFinite(n.y)) continue;
      const p = projectNode(n, projection);
      map.set(n.id, { id: n.id, x: p.x, y: p.y });
    }
    positionsRef.current = map;
    setPositionsTick((t) => t + 1);
  }, [graph, projection]);

  const positions = positionsRef.current;

  const edgeTimes = useMemo(() => {
    const times = new Map<string, number>();
    for (const edge of graph?.edges ?? []) {
      times.set(`${edge.source}->${edge.target}`, edge.travel_time);
    }
    return times;
  }, [graph]);

  const activeEdges = useMemo(() => {
    const set = new Set<string>();
    if (!route) return set;
    for (let i = 0; i < route.road_node_sequence.length - 1; i++) {
      set.add(`${route.road_node_sequence[i]}->${route.road_node_sequence[i + 1]}`);
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
    const node = (graph.nodes as NodeData[]).find((n) => n.id === hoverNodeId);
    if (!node) return null;
    let servedOrderCount = 0;
    if (route && route.stop_sequence.includes(hoverNodeId)) {
      servedOrderCount = route.served_order_ids.length;
    }
    return {
      node,
      onRoute: activeNodeIds.has(node.id),
      servedOrderCount,
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

  if (!projection) {
    return (
      <div className="map-empty">
        <div>
          <strong>场景数据非法</strong>
          <br />
          节点缺少有效的 <code>x</code> / <code>y</code> 坐标。
        </div>
      </div>
    );
  }

  const hoverPos = hoverNodeId ? positions.get(hoverNodeId) : null;

  return (
    <svg
      className="map-svg"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="配送网络示意图"
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

      {/* 1. 物流边（开关控制） */}
      {(
        <NetworkEdgeLayer
          positions={positions}
          edges={graph.edges as EdgeData[]}
          activeEdges={activeEdges}
          showNetworkEdges={showNetworkEdges}
        />
      )}

      {/* 2. 物流节点 */}
      <NetworkNodeLayer
        nodes={graph.nodes as NodeData[]}
        positions={positions}
        activeNodeIds={activeNodeIds}
        hoverNodeId={hoverNodeId}
        timelineHighlightId={activeTimelineNodeId}
        onHover={handleHover}
      />

      {/* 3. 完成标记（绿色小勾） */}
      {completedStops && completedStops.size > 0 && (
        <g className="completed-marks" aria-hidden>
          {Array.from(completedStops).map((id) => {
            const pos = positions.get(id);
            if (!pos) return null;
            return (
              <g key={`completed-${id}`} transform={`translate(${pos.x + 10}, ${pos.y - 10})`}>
                <circle r={9} fill="var(--status-good)" stroke="var(--surface-panel)" strokeWidth={1.5} />
                <path
                  d="M -3.5 0 L -1 2.5 L 3.5 -2.5"
                  fill="none"
                  stroke="var(--text-on-accent)"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </g>
            );
          })}
        </g>
      )}

      {/* 4. 实时回放：车辆标记（橙色填充圆） */}
      {vehiclePosition && (() => {
        const point = positionOnRoadPath(vehiclePosition.path, vehiclePosition.t, positions, edgeTimes);
        if (!point) return null;
        return (
          <g className="vehicle-marker" aria-label="当前车辆位置">
            <circle cx={point.x} cy={point.y} r={10} fill="var(--accent-primary)" fillOpacity={0.18} />
            <circle cx={point.x} cy={point.y} r={5} fill="var(--accent-primary)" stroke="var(--surface-panel)" strokeWidth={2} />
          </g>
        );
      })()}

      {/* 5. 节点悬停 tooltip（HTML overlay） */}
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
              类型：{hoverInfo.node.type}
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
