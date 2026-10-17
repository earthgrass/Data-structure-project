// Phase 5 —— 双目标比较面板（distance vs cost，不再比较三种调度算法）。

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
        <h3>双目标比较 <span className="meta">点击「双目标比较」生成</span></h3>
      </div>
    );
  }
  return (
    <div className="comparison">
      <h3>
        双目标比较
        <span className="meta">
          同场景快照 · 主目标 {data.objectives.join(' + ')}
        </span>
      </h3>
      <table className="comparison-table">
        <thead>
          <tr>
            <th>指标</th>
            {data.objectives.map((o) => (
              <th key={o}>{OBJECTIVE_LABELS[o] ?? o}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>已配送 / 总订单</td>
            {data.objectives.map((o) => {
              const r = data.results[o];
              const total = r.served_order_ids.length + r.unserved_orders.length;
              return (
                <td key={o}>
                  <span className={r.is_feasible ? 'good' : 'bad'}>
                    {r.served_order_ids.length}/{total}
                  </span>
                </td>
              );
            })}
          </tr>
          <tr>
            <td>总距离</td>
            {data.objectives.map((o) => (
              <td key={o}>{data.results[o].total_distance.toFixed(2)}</td>
            ))}
          </tr>
          <tr>
            <td>总时间</td>
            {data.objectives.map((o) => (
              <td key={o}>{data.results[o].total_travel_time.toFixed(2)}</td>
            ))}
          </tr>
          <tr>
            <td>总成本</td>
            {data.objectives.map((o) => (
              <td key={o}>{data.results[o].total_cost.toFixed(2)}</td>
            ))}
          </tr>
          <tr>
            <td>主目标</td>
            {data.objectives.map((o) => (
              <td key={o}>{data.results[o].main_objective_total.toFixed(2)}</td>
            ))}
          </tr>
          <tr>
            <td>规划耗时(s)</td>
            {data.objectives.map((o) => (
              <td key={o}>
                {data.results[o].planning_stats.runtime_seconds.toFixed(3)}
              </td>
            ))}
          </tr>
          <tr>
            <td>可行性</td>
            {data.objectives.map((o) => {
              const r = data.results[o];
              return (
                <td key={o}>
                  <span className={r.is_feasible ? 'good' : 'bad'}>
                    {r.is_feasible ? 'feasible ✓' : 'infeasible ✗'}
                  </span>
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
    </div>
  );
}