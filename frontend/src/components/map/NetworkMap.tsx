// Phase 5.3 —— NetworkMap：路线网络示意图容器。
// 内含：顶部工具栏（场景名 + 站点段数 + 边开关）+ RouteSchematic + 图例。
// 校验器状态（PASS/FAIL）已迁移到 SideNav 数据区（Phase 5.3+）。

import { useEffect, useState } from 'react';
import type { GraphData, RoutePlanData, ScheduleResult } from '../../types';
import { RouteSchematic } from './RouteSchematic';
import { MapLegend } from './MapLegend';

interface NetworkMapProps {
  graph: GraphData | null;
  route: RoutePlanData | null;
  /** 已废弃：校验状态由 SideNav 展示；保留字段以兼容调用方 */
  validation?: unknown;
  scenarioName: string | null;
  /** 当前展示结果的目标 / 计划摘要（用于工具栏右上角状态徽章） */
  resultSummary: ScheduleResult | null;
  /** 时间轴联动高亮 */
  activeTimelineNodeId?: string | null;
  onNodeHover?: (nodeId: string | null) => void;
}

export function NetworkMap({
  graph,
  route,
  scenarioName,
  resultSummary,
  activeTimelineNodeId,
  onNodeHover,
}: NetworkMapProps) {
  const [showEdges, setShowEdges] = useState(true);
  // 场景变化时默认重新开启边显示
  useEffect(() => {
    setShowEdges(true);
  }, [scenarioName]);

  const stopsCount = route?.stop_sequence.length ?? 0;

  return (
    <div className="map-panel" role="region" aria-label="配送网络示意图">
      <div className="map-toolbar">
        <div className="map-title">配送网络</div>
        <div className="map-toolbar-meta">
          {scenarioName && (
            <span>
              <strong style={{ color: 'var(--text-secondary)' }}>
                场景：
              </strong>
              {scenarioName}
            </span>
          )}
          {stopsCount > 0 && (
            <span>站点 {stopsCount - 1} 段</span>
          )}
          <label className="map-toggle" title="切换显示普通网络边">
            <input
              type="checkbox"
              checked={showEdges}
              onChange={(e) => setShowEdges(e.target.checked)}
            />
            显示网络边
          </label>
        </div>
      </div>

      <div className="map-canvas">
        <RouteSchematic
          graph={graph}
          route={route}
          showNetworkEdges={showEdges}
          activeTimelineNodeId={activeTimelineNodeId ?? null}
          onNodeHover={onNodeHover}
        />
        {resultSummary && (
          <MapLegend showNetworkEdges={showEdges} />
        )}
      </div>
    </div>
  );
}