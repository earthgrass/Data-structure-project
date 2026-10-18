// Phase 5.3 —— NetworkMap：路线网络示意图容器。
// 顶部工具栏、等比缩放的 RouteSchematic 与底部图例。

import { useEffect, useState } from 'react';
import type { GraphData, RoutePlanData } from '../../types';
import { RouteSchematic } from './RouteSchematic';
import { MapLegend } from './MapLegend';

interface NetworkMapProps {
  graph: GraphData | null;
  route: RoutePlanData | null;
  scenarioName: string | null;
  /** 时间轴联动高亮 */
  activeTimelineNodeId?: string | null;
  onNodeHover?: (nodeId: string | null) => void;
  /** 实时回放：车辆位置 */
  vehiclePosition?: { path: string[]; t: number } | null;
  /** 实时回放：已完成的站点集合 */
  completedStops?: ReadonlySet<string>;
}

export function NetworkMap({
  graph,
  route,
  scenarioName,
  activeTimelineNodeId,
  onNodeHover,
  vehiclePosition = null,
  completedStops,
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
          {stopsCount > 0 && (
            <span>路线 {stopsCount - 1} 段</span>
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
          vehiclePosition={vehiclePosition}
          completedStops={completedStops}
        />
      </div>
      <MapLegend showNetworkEdges={showEdges} />
    </div>
  );
}
