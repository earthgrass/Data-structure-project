// Phase 5.1 —— NetworkMap：地图主视觉容器。
// 内含：顶部工具栏（场景 / seed / 车辆 / 目标 / 边开关）+ BeijingMap + 图例 + 免责声明。

import { useEffect, useState } from 'react';
import type { GraphData, RoutePlanData, ScheduleResult, ValidationReport } from '../../types';
import { BeijingMap } from '../BeijingMap';
import { MapLegend } from './MapLegend';

interface NetworkMapProps {
  graph: GraphData | null;
  route: RoutePlanData | null;
  validation: ValidationReport | null;
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
  validation,
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

  const feasibility = validation?.feasible ?? null;
  const stopsCount = route?.stop_sequence.length ?? 0;

  return (
    <div className="map-panel" role="region" aria-label="物流网络地图">
      <div className="map-toolbar">
        <div className="map-title">路网地图 · 示意场景</div>
        <div className="map-toolbar-meta">
          {scenarioName && (
            <span>
              <strong style={{ color: 'var(--text-secondary)' }}>
                场景：
              </strong>
              {scenarioName}
            </span>
          )}
          {feasibility != null && (
            <span
              className={`badge ${feasibility ? 'badge-feasible' : 'badge-infeasible'}`}
              style={{ padding: '2px 8px', fontSize: 10 }}
            >
              <span className="dot" />
              {feasibility ? 'validator PASS' : 'validator FAIL'}
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
        <BeijingMap
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

      <div className="map-disclaimer">
        地图区域基于北京 16 区示意 GeoJSON 投影，节点坐标由 Phase 4 随机场景生成器产出，
        边权为系统生成的课程设计数据；不代表真实行政区划或真实道路导航结果。
      </div>
    </div>
  );
}
