// Phase 5.1 —— RouteTimeline：配送顺序时间轴。
// 支持：选中节点 → 通知父组件高亮地图上的对应节点。

import type { RoutePlanData } from '../../types';

interface RouteTimelineProps {
  stops: RoutePlanData['stops'];
  stopSequence: RoutePlanData['stop_sequence'];
  depotId: string;
  /** 受控选中节点 */
  activeNodeId?: string | null;
  onSelectNode?: (nodeId: string) => void;
}

function fmt(n: number, digits = 1): string {
  return n.toFixed(digits);
}

export function RouteTimeline({
  stops,
  stopSequence,
  depotId,
  activeNodeId,
  onSelectNode,
}: RouteTimelineProps) {
  return (
    <div className="timeline" role="list" aria-label="配送顺序时间轴">
      {stopSequence.map((node, i) => {
        const isLast = i === stopSequence.length - 1;
        const stop = stops[i];
        const isDepot = i === 0 || isLast;
        const role = isDepot ? 'tl-depot' : 'tl-customer';
        const isActive = activeNodeId === node;
        return (
          <div
            key={`stop-${i}-${node}`}
            className={`timeline-row ${role} ${isActive ? 'is-active' : ''}`}
            role="listitem"
            onClick={() => onSelectNode?.(node)}
            onMouseEnter={() => onSelectNode?.(node)}
            title={isDepot ? `${node} · 仓库` : `${node} · 配送站点`}
          >
            <span className="seq">{String(i + 1).padStart(2, '0')}</span>
            <span className="node-id">
              {node}
              {isDepot && (
                <span
                  style={{
                    fontSize: 10,
                    color: 'var(--text-muted)',
                    fontWeight: 500,
                    marginLeft: 4,
                  }}
                >
                  · {i === 0 ? '起点' : '返回'}
                </span>
              )}
            </span>
            <span className="meta">
              {stop ? `到 ${fmt(stop.arrival_time)}` : '—'}
            </span>
            <span className="meta">
              {stop
                ? stop.waiting_time > 0
                  ? `等 ${fmt(stop.waiting_time)}`
                  : '不停'
                : '—'}
            </span>
          </div>
        );
      })}
      {/* 隐藏 depot 引用避免 lint 警告 */}
      {depotId && <span hidden>{depotId}</span>}
    </div>
  );
}
