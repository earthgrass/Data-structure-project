// Phase 5.1 —— RouteLegDetails：路线段详情表。
// 每段展示：起点 → 终点 / 主指标 / 时间 / 成本。
// 数据来自 ScheduleResult.route_plan.legs。

import type { LegData } from '../../types';

interface RouteLegDetailsProps {
  legs: LegData[];
  /** 主目标（用于高亮对应的 cross_metrics 字段） */
  mainObjective: string;
}

function fmt(n: number, digits = 2): string {
  return n.toFixed(digits);
}

function getLegMetric(leg: LegData, key: string): number {
  if (key === 'distance') return leg.total_weight;
  return leg.cross_metrics?.[key] ?? NaN;
}

export function RouteLegDetails({ legs, mainObjective }: RouteLegDetailsProps) {
  if (legs.length === 0) {
    return (
      <div className="muted" style={{ fontSize: 'var(--font-xs)' }}>
        无路段数据
      </div>
    );
  }

  return (
    <div className="leg-list" role="list" aria-label="路线段详情">
      {legs.map((leg, idx) => {
        const distance = getLegMetric(leg, 'distance');
        const time = getLegMetric(leg, 'travel_time');
        const cost = getLegMetric(leg, 'cost');
        return (
          <div
            className="leg-row"
            key={`leg-${idx}-${leg.source}-${leg.target}`}
            role="listitem"
          >
            <span className="leg-idx">#{idx + 1}</span>
            <span
              className="leg-endpoints"
              title={`${leg.source} → ${leg.target}（${leg.path.length} 个节点）`}
            >
              <strong>{leg.source}</strong>
              <span className="arrow">→</span>
              <strong>{leg.target}</strong>
            </span>
            <span
              className="leg-metric"
              style={
                mainObjective === 'distance'
                  ? { color: 'var(--text-primary)', fontWeight: 700 }
                  : undefined
              }
              title="距离"
            >
              {Number.isFinite(distance) ? fmt(distance) : '—'}
            </span>
            <span
              className="leg-metric"
              title="时间"
            >
              {Number.isFinite(time) ? fmt(time) : '—'}
            </span>
            <span
              className="leg-metric"
              style={
                mainObjective === 'cost'
                  ? { color: 'var(--text-primary)', fontWeight: 700 }
                  : undefined
              }
              title="成本"
            >
              {Number.isFinite(cost) ? fmt(cost) : '—'}
            </span>
          </div>
        );
      })}
    </div>
  );
}
