// Phase 5 验收整改 —— ObjectiveComparison：并排双卡片。

import type { CompareResponse } from '../../types';

interface ObjectiveComparisonProps {
  data: CompareResponse | null;
}

const OBJECTIVE_LABELS: Record<string, string> = {
  distance: '最短距离',
  cost: '最低成本',
};

export function ObjectiveComparison({ data }: ObjectiveComparisonProps) {
  if (!data) {
    return (
      <div className="comparison">
        <div className="comparison-head">
          <h3>双目标比较</h3>
          <span className="meta">点击「双目标比较」生成</span>
        </div>
      </div>
    );
  }

  // 两张并排卡片，每张一个目标
  const cards = data.objectives.map((obj) => {
    const r = data.results[obj];
    const isFull = r.unserved_orders.length === 0;
    return (
      <div
        key={obj}
        className={`comparison-card ${obj === 'cost' ? 'cost-card' : ''}`}
      >
        <h4>
          {OBJECTIVE_LABELS[obj] ?? obj}
          <span className="objective-tag">{obj}</span>
        </h4>
        <div className={`row ${isFull ? 'is-good' : 'is-bad'}`}>
          <span className="k">已配送 / 总订单</span>
          <span className="v">
            {r.served_order_ids.length} / {r.served_order_ids.length + r.unserved_orders.length}
          </span>
        </div>
        <div className="row">
          <span className="k">总距离</span>
          <span className="v">{r.total_distance.toFixed(2)}</span>
        </div>
        <div className="row">
          <span className="k">总时间</span>
          <span className="v">{r.total_travel_time.toFixed(2)}</span>
        </div>
        <div className="row">
          <span className="k">总成本</span>
          <span className="v">{r.total_cost.toFixed(2)}</span>
        </div>
        <div className="row">
          <span className="k">主目标值</span>
          <span className="v">{r.main_objective_total.toFixed(2)}</span>
        </div>
        <div className="row">
          <span className="k">规划耗时 (s)</span>
          <span className="v">{r.planning_stats.runtime_seconds.toFixed(3)}</span>
        </div>
        <div className={`row ${r.is_feasible ? 'is-good' : 'is-bad'}`}>
          <span className="k">可行性</span>
          <span className="v">{r.is_feasible ? '✓ feasible' : '✗ infeasible'}</span>
        </div>
      </div>
    );
  });

  return (
    <div className="comparison">
      <div className="comparison-head">
        <h3>双目标比较</h3>
        <span className="meta">
          同场景快照 · 两种主目标统一规划器（CFI + 2-opt）
        </span>
      </div>
      <div className="comparison-cards">{cards}</div>
    </div>
  );
}