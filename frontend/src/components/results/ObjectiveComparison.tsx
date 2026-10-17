// Phase 5.1 —— ObjectiveComparison：双目标对比。
// 完整对比表 + 摘要卡片；强调"两种方案互不宣称更优"。

import type { CompareResponse, ScheduleResult } from '../../types';

interface ObjectiveComparisonProps {
  data: CompareResponse | null;
  scenarioName?: string | null;
  /** 错误信息（任一目标失败时显示） */
  errorMessage?: string | null;
}

interface Row {
  key: string;
  label: string;
  format: (r: ScheduleResult) => string;
  goodWhen?: (r: ScheduleResult) => boolean;
}

function fmtNum(n: number, digits = 2): string {
  return n.toFixed(digits);
}

const OBJECTIVE_LABEL: Record<string, string> = {
  distance: '最短距离',
  cost: '最低成本',
};

const ROWS: Row[] = [
  {
    key: 'served',
    label: '已配送 / 总订单',
    format: (r) =>
      `${r.served_order_ids.length} / ${
        r.served_order_ids.length + r.unserved_orders.length
      }`,
    goodWhen: (r) => r.unserved_orders.length === 0,
  },
  {
    key: 'unserved',
    label: '未配送',
    format: (r) => String(r.unserved_orders.length),
    goodWhen: (r) => r.unserved_orders.length === 0,
  },
  {
    key: 'distance',
    label: '总距离',
    format: (r) => fmtNum(r.total_distance),
    goodWhen: (r) => r.objective === 'distance' || false,
  },
  {
    key: 'time',
    label: '总时间',
    format: (r) => fmtNum(r.total_travel_time),
  },
  {
    key: 'cost',
    label: '总成本',
    format: (r) => fmtNum(r.total_cost),
    goodWhen: (r) => r.objective === 'cost' || false,
  },
  {
    key: 'main',
    label: '主目标值',
    format: (r) => fmtNum(r.main_objective_total),
  },
  {
    key: 'feasible',
    label: '可行性',
    format: (r) => (r.is_feasible ? '✓ 可行' : '✗ 不可行'),
    goodWhen: (r) => r.is_feasible,
  },
  {
    key: 'runtime',
    label: '规划耗时 (s)',
    format: (r) => fmtNum(r.planning_stats.runtime_seconds, 3),
  },
];

function computeDelta(a: number, b: number): { sign: 'pos' | 'neg' | 'zero'; text: string } {
  if (!Number.isFinite(a) || !Number.isFinite(b) || a === b) {
    return { sign: 'zero', text: '—' };
  }
  const diff = b - a;
  const pct = a === 0 ? 0 : (diff / a) * 100;
  const sign = diff > 0 ? 'pos' : 'neg';
  // 对比列：以 distance 为基准；正值表示 cost 比 distance 大
  const arrow = diff > 0 ? '↑' : '↓';
  return {
    sign,
    text: `${arrow} ${Math.abs(pct).toFixed(2)}%`,
  };
}

export function ObjectiveComparison({
  data,
  scenarioName,
  errorMessage,
}: ObjectiveComparisonProps) {
  const objectives = data?.objectives ?? [];
  const results = data?.results ?? {};

  const distanceRes = results['distance'];
  const costRes = results['cost'];

  return (
    <div className="comparison" role="region" aria-label="双目标对比">
      <div className="comparison-head">
        <h3>双目标对比</h3>
        <span className="meta">
          同一场景快照 · 两种主目标统一规划器（CFI + 2-opt）
          {scenarioName && (
            <>
              {' · 场景 '}
              <strong style={{ color: 'var(--text-secondary)' }}>
                {scenarioName}
              </strong>
            </>
          )}
        </span>
      </div>

      {!data ? (
        <div className="comparison-empty">
          点击「双目标比较」对当前场景的距离 / 成本目标并行规划并对比结果。
        </div>
      ) : objectives.length < 2 || !distanceRes || !costRes ? (
        <div className="comparison-empty">
          {errorMessage ? (
            <span className="error-text">{errorMessage}</span>
          ) : (
            <span>对比结果不完整：仅 {objectives.length} 个目标返回结果，无法形成对比。</span>
          )}
        </div>
      ) : (
        <div className="comparison-body">
          <table className="comparison-table">
            <thead>
              <tr>
                <th className="metric-col">指标</th>
                <th className="col-distance">
                  {OBJECTIVE_LABEL['distance']}
                  <br />
                  <span
                    style={{
                      color: 'var(--text-muted)',
                      fontWeight: 500,
                      fontSize: 10,
                    }}
                  >
                    主目标：distance
                  </span>
                </th>
                <th className="col-cost">
                  {OBJECTIVE_LABEL['cost']}
                  <br />
                  <span
                    style={{
                      color: 'var(--text-muted)',
                      fontWeight: 500,
                      fontSize: 10,
                    }}
                  >
                    主目标：cost
                  </span>
                </th>
                <th className="col-delta">差异（cost vs distance）</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row) => {
                const a = row.format(distanceRes);
                const b = row.format(costRes);
                const aGood = row.goodWhen?.(distanceRes) ?? false;
                const bGood = row.goodWhen?.(costRes) ?? false;
                // 数值差异（仅对数字型）
                let delta: { sign: 'pos' | 'neg' | 'zero'; text: string } = {
                  sign: 'zero',
                  text: '—',
                };
                if (row.key === 'distance') {
                  delta = computeDelta(distanceRes.total_distance, costRes.total_distance);
                } else if (row.key === 'time') {
                  delta = computeDelta(
                    distanceRes.total_travel_time,
                    costRes.total_travel_time,
                  );
                } else if (row.key === 'cost') {
                  delta = computeDelta(distanceRes.total_cost, costRes.total_cost);
                } else if (row.key === 'main') {
                  // 主目标值不可直接对比（不同语义）
                  delta = { sign: 'zero', text: '不同语义' };
                } else if (row.key === 'runtime') {
                  delta = computeDelta(
                    distanceRes.planning_stats.runtime_seconds,
                    costRes.planning_stats.runtime_seconds,
                  );
                } else if (row.key === 'unserved') {
                  delta = { sign: 'zero', text: '—' };
                }
                return (
                  <tr key={`row-${row.key}`}>
                    <td className="metric-col">{row.label}</td>
                    <td className={aGood ? 'value-good' : ''}>{a}</td>
                    <td className={bGood ? 'value-good' : ''}>{b}</td>
                    <td
                      className={
                        delta.sign === 'pos'
                          ? 'delta-pos'
                          : delta.sign === 'neg'
                          ? 'delta-neg'
                          : 'delta-neutral'
                      }
                    >
                      {delta.text}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
