// Phase 5 验收整改 —— ResultPanel：完整 KPI 卡片 + 状态概览 + 路线时间轴。

import type { ScheduleResult } from '../../types';

interface ResultPanelProps {
  result: ScheduleResult | null;
  objective: string | null;
  emptyMessage?: string;
}

function fmtNum(n: number, digits: number = 2): string {
  return n.toFixed(digits);
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
  const isFull = unservedCount === 0;
  const stats = result.planning_stats;

  return (
    <div className="panel result">
      <h2>调度结果{objective ? ` · ${objective}` : ''}</h2>

      {/* KPI 卡片 */}
      <div className="kpi-grid">
        <div className={`kpi ${isFull ? 'kpi-good' : 'kpi-bad'} kpi-full`}>
          <div className="kpi-label">已配送 / 总订单</div>
          <div className="kpi-value">
            {servedCount}
            <span className="kpi-suffix">/ {totalOrders}</span>
          </div>
        </div>

        <div className={`kpi ${unservedCount === 0 ? 'kpi-good' : 'kpi-bad'}`}>
          <div className="kpi-label">未配送</div>
          <div className="kpi-value">{unservedCount}</div>
        </div>

        <div className="kpi">
          <div className="kpi-label">总距离</div>
          <div className="kpi-value">{fmtNum(result.total_distance)}</div>
        </div>

        <div className="kpi">
          <div className="kpi-label">总时间</div>
          <div className="kpi-value">{fmtNum(result.total_travel_time)}</div>
        </div>

        <div className="kpi">
          <div className="kpi-label">总成本</div>
          <div className="kpi-value">{fmtNum(result.total_cost)}</div>
        </div>

        <div className={`kpi ${result.is_feasible ? 'kpi-good' : 'kpi-bad'}`}>
          <div className="kpi-label">可行性</div>
          <div className="kpi-value">{result.is_feasible ? '✓ 可行' : '✗ 不可行'}</div>
        </div>
      </div>

      {/* 状态概览 */}
      <div className="panel-section">
        <div className="section-title">方案概览</div>
        <ul className="status-list">
          <li>
            <span className="key">主目标</span>
            <span className="val">{result.objective}</span>
          </li>
          <li>
            <span className="key">主目标值</span>
            <span className="val">{fmtNum(result.main_objective_total)}</span>
          </li>
          <li>
            <span className="key">车辆</span>
            <span className="val">{result.vehicle_id}</span>
          </li>
          <li>
            <span className="key">仓库</span>
            <span className="val">{result.depot_id}</span>
          </li>
          <li>
            <span className="key">调度耗时</span>
            <span className="val">{fmtNum(stats.runtime_seconds, 3)} s</span>
          </li>
          <li>
            <span className="key">Dijkstra 调用</span>
            <span className="val">{stats.dijkstra_calls}</span>
          </li>
          <li>
            <span className="key">缓存命中</span>
            <span className="val">{stats.cache_hits}</span>
          </li>
          <li>
            <span className="key">可行性校验</span>
            <span className="val">{stats.feasibility_checks}</span>
          </li>
        </ul>
      </div>

      {/* 错误订单（如果有） */}
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

      {/* 路线时间轴 */}
      <div className="panel-section">
        <div className="section-title">配送顺序 · {result.route_plan.stop_sequence.length - 1} 段</div>
        <div className="timeline">
          {result.route_plan.stop_sequence.map((node, i) => {
            const isLast = i === result.route_plan.stop_sequence.length - 1;
            const stop = result.route_plan.stops[i];
            const isDepot = i === 0 || isLast;
            const role = isDepot ? 'tl-depot' : 'tl-customer';
            return (
              <div key={`stop-${i}`} className={`timeline-row ${role}`}>
                <span className="seq">{String(i + 1).padStart(2, '0')}</span>
                <span className="node-id">{node}</span>
                <span className="meta">
                  {stop && `t=${fmtNum(stop.arrival_time, 1)}`}
                </span>
                <span className="meta">
                  {stop && stop.waiting_time > 0
                    ? `等 ${fmtNum(stop.waiting_time, 1)}`
                    : '无需等'}
                </span>
                <span className="meta">
                  {stop && `${fmtNum(stop.service_start, 1)}→${fmtNum(stop.service_end, 1)}`}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}