// ComparisonTable —— 底部三算法对照表。

import type { ScheduleResult } from '../types';

interface ComparisonTableProps {
  results: Record<string, ScheduleResult> | null;
  objective: string;
}

const ALGO_LABELS: Record<string, string> = {
  nearest_neighbor: '最近邻 NN',
  insertion: '可行插入 CFI',
  two_opt: '受约束 2-opt',
};

export function ComparisonTable({ results, objective }: ComparisonTableProps) {
  if (!results || Object.keys(results).length === 0) {
    return (
      <div className="comparison">
        <strong>三算法比较</strong> — 尚无对比结果，点击"三算法比较"按钮生成。
      </div>
    );
  }

  const algos = Object.keys(results);

  return (
    <div className="comparison">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <strong>三算法比较（同场景 · 主目标 {objective}）</strong>
        <span style={{ color: '#6c7079', fontSize: 11 }}>
          同一随机场景 + 同主目标；travel_time / cost / distance 在每行完整展示
        </span>
      </div>
      <table className="comparison-table">
        <thead>
          <tr>
            <th>算法</th>
            <th>已配送</th>
            <th>总距离</th>
            <th>总时间</th>
            <th>总成本</th>
            <th>主目标</th>
            <th>耗时(s)</th>
            <th>可行性</th>
          </tr>
        </thead>
        <tbody>
          {algos.map((algo) => {
            const r = results[algo];
            return (
              <tr key={algo} className={r.is_feasible ? 'feasible' : 'infeasible'}>
                <td>{ALGO_LABELS[algo] ?? algo}</td>
                <td>
                  {r.served_order_ids.length}/{r.served_order_ids.length + r.unserved_orders.length}
                </td>
                <td>{r.total_distance.toFixed(2)}</td>
                <td>{r.total_travel_time.toFixed(2)}</td>
                <td>{r.total_cost.toFixed(2)}</td>
                <td>{r.main_objective_total.toFixed(2)}</td>
                <td>{r.planning_stats.runtime_seconds.toFixed(3)}</td>
                <td>{r.is_feasible ? 'feasible ✓' : 'infeasible ✗'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}