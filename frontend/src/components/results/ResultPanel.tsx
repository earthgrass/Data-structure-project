// Phase 5 —— 右侧调度结果面板：指标 + 路线时间表 + 统计。

import type { ScheduleResult } from '../../types';

interface ResultPanelProps {
  result: ScheduleResult | null;
  objective: string | null;
  emptyMessage?: string;
}

export function ResultPanel({ result, objective, emptyMessage }: ResultPanelProps) {
  if (!result) {
    return (
      <div className="panel result">
        <h2>调度结果</h2>
        <p className="empty-state">{emptyMessage ?? '尚无调度结果。'}</p>
      </div>
    );
  }

  const servedCount = result.served_order_ids.length;
  const unservedCount = result.unserved_orders.length;
  const totalOrders = servedCount + unservedCount;

  return (
    <div className="panel result">
      <h2>调度结果{objective ? ` · ${objective}` : ''}</h2>

      <div className="metric-grid">
        <div className={`metric ${result.is_feasible ? 'good' : 'bad'}`}>
          <div className="label">已配送</div>
          <div className="value">{servedCount}/{totalOrders}</div>
        </div>
        <div className={`metric ${unservedCount === 0 ? 'good' : 'bad'}`}>
          <div className="label">未配送</div>
          <div className="value">{unservedCount}</div>
        </div>
        <div className="metric">
          <div className="label">总距离</div>
          <div className="value">{result.total_distance.toFixed(2)}</div>
        </div>
        <div className="metric">
          <div className="label">总时间</div>
          <div className="value">{result.total_travel_time.toFixed(2)}</div>
        </div>
        <div className="metric">
          <div className="label">总成本</div>
          <div className="value">{result.total_cost.toFixed(2)}</div>
        </div>
        <div className={`metric ${result.is_feasible ? 'good' : 'bad'}`}>
          <div className="label">可行性</div>
          <div className="value">{result.is_feasible ? '✓' : '✗'}</div>
        </div>
      </div>

      <div style={{
          fontSize: 12, color: 'var(--text-secondary)',
          marginBottom: 6,
        }}>
        车辆 <strong>{result.vehicle_id}</strong> ·
        仓库 <strong>{result.depot_id}</strong> ·
        主目标 <strong>{result.objective}</strong>（实际 {result.main_objective_total.toFixed(2)}）
      </div>

      <div style={{
          fontSize: 12, color: 'var(--text-secondary)',
          marginBottom: 6,
        }}>
        耗时：调度 {result.planning_stats.runtime_seconds.toFixed(3)} s ·{' '}
        Dijkstra 调用 {result.planning_stats.dijkstra_calls} ·{' '}
        缓存命中 {result.planning_stats.cache_hits} ·{' '}
        可行性校验 {result.planning_stats.feasibility_checks}
      </div>

      {result.unserved_orders.length > 0 && (
        <div className="error-banner">
          <strong>未配送订单（{unservedCount}）：</strong>
          <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
            {result.unserved_orders.map((v) => (
              <li key={v.order_id}>
                {v.order_id} — <em>{v.kind}</em>：{v.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div style={{
          fontSize: 12, color: 'var(--text-secondary)',
          marginTop: 8, marginBottom: 4,
        }}>
        配送顺序（{result.route_plan.stop_sequence.length - 1} 段 → 闭合回路）：
      </div>
      <div className="route-timeline">
        {result.route_plan.stop_sequence.map((node, i) => {
          const isLast = i === result.route_plan.stop_sequence.length - 1;
          const stop = result.route_plan.stops[i];
          const isDepot = i === 0 || isLast;
          return (
            <div key={`stop-${i}`} className={`route-step ${isDepot ? 'depot' : 'customer'}`}>
              <span className="step-id">{String(i + 1).padStart(2, '0')}. {node}</span>
              {stop && (
                <span className="step-meta">
                  t={stop.arrival_time.toFixed(1)}
                  {stop.waiting_time > 0 && ` · wait ${stop.waiting_time.toFixed(1)}`}
                </span>
              )}
              <span className="step-meta">
                {stop && `服务 ${stop.service_start.toFixed(1)} → ${stop.service_end.toFixed(1)}`}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}