// Phase 5.2 —— ResultPanel：右侧调度结果面板。
//
// 数据归属（受 FinAgent-X V2 工程实践启发）：
//   - OWN：KPI 卡片（2×3）、方案概览、配送时间轴、路段详情
//   - NOT OWN：不调用任何 API；所有 result 数据来自 props
//   - DISPLAY：完全受控；result / errorMessage 均由父组件传入
//   - 严禁显示 stale 数据冒充 fresh：只在 result 非空时展示完整内容
//     空状态由 EmptyState 接管

import type { Objective, ScheduleResult } from '../../types';
import type { PlaybackView } from '../../state/usePlayback';
import { EmptyState, ErrorState } from '../shared/EmptyState';
import { RouteTimeline } from './RouteTimeline';
import { RouteLegDetails } from './RouteLegDetails';
import { PlaybackStrip } from './PlaybackStrip';

interface ResultPanelProps {
  result: ScheduleResult | null;
  isLoading?: boolean;
  objective: Objective | null;
  hasScenario: boolean;
  /** 当前选中节点（受控；用于时间轴 ↔ 地图联动） */
  activeTimelineNodeId?: string | null;
  onSelectTimelineNode?: (nodeId: string | null) => void;
  errorMessage?: string | null;
  onRetry?: () => void;
  /** 实时回放视图；null / undefined 时不渲染 PlaybackStrip */
  playback?: PlaybackView | null;
}

function fmtNum(n: number, digits = 2): string {
  return Number.isFinite(n) ? n.toFixed(digits) : '—';
}

const OBJECTIVE_LABEL: Record<string, string> = {
  distance: '最短距离',
  cost: '最低成本',
};

export function ResultPanel({
  result,
  isLoading = false,
  objective,
  hasScenario,
  activeTimelineNodeId,
  onSelectTimelineNode,
  errorMessage,
  onRetry,
  playback,
}: ResultPanelProps) {
  // 错误状态（最高优先）
  if (errorMessage) {
    return (
      <div className="panel result panel-scroll" role="region" aria-label="调度结果">
        <ErrorState title="规划失败" message={errorMessage} onRetry={onRetry} />
      </div>
    );
  }

  if (isLoading) return <section className="panel result" aria-label="调度结果" aria-busy="true"><h2 className="panel-h2">调度结果</h2><div className="result-empty" role="status"><span className="loading-dot" />正在生成配送方案…<p>校验容量、时间窗与闭合路线。</p></div></section>;

  // 空状态
  if (!result) {
    return (
      <div className="panel result panel-scroll" role="region" aria-label="调度结果">
        <h2 className="panel-h2">
          <span>调度结果</span>
          <span className="badge badge-neutral">未运行</span>
        </h2>
        <EmptyState
          title="尚未生成配送方案"
          description={
            hasScenario
              ? '在左侧选择目标，点击「运行规划」。'
              : '请先在左侧生成场景。'
          }
          illustration={
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
              <path
                d="M5 4h14l-2 9H7L5 4zM5 4L3 2M9 13v4h6v-4"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle cx="9.5" cy="18.5" r="1.5" fill="currentColor" />
              <circle cx="16.5" cy="18.5" r="1.5" fill="currentColor" />
            </svg>
          }
        />
      </div>
    );
  }

  const servedCount = result.served_order_ids.length;
  const unservedCount = result.unserved_orders.length;
  const totalOrders = servedCount + unservedCount;
  const isFull = unservedCount === 0;
  const stats = result.planning_stats;
  const route = result.route_plan;
  const obj = result.objective ?? objective ?? 'distance';

  return (
    <div className="panel result panel-scroll" role="region" aria-label="调度结果">
      <h2 className="panel-h2">
        <span>调度结果 · {OBJECTIVE_LABEL[obj] ?? obj}</span>
        {result.is_feasible ? (
          <span className="badge badge-feasible">
            <span className="dot" />
            可行
          </span>
        ) : (
          <span className="badge badge-infeasible">
            <span className="dot" />
            不可行
          </span>
        )}
      </h2>

      {/* 播放中、单段到站暂停及完成后均保留累计指标。 */}
      {playback && (playback.isPlaying || playback.isPaused || playback.isDone) && (
        <PlaybackStrip playback={playback} />
      )}

      {/* KPI 卡片 2×3 */}
      <div className="kpi-grid">
        <div
          className={`kpi ${isFull ? '' : 'kpi-bad'}`}
          title={isFull ? '全部订单已完成配送' : `${unservedCount} 个订单未配送`}
        >
          <div className="kpi-label">已配送 / 总订单</div>
          <div className="kpi-value">
            {servedCount}
            <span className="kpi-suffix">/ {totalOrders}</span>
          </div>
        </div>

        <div
          className={`kpi ${unservedCount === 0 ? 'kpi-good' : 'kpi-bad'}`}
          title="未配送订单数"
        >
          <div className="kpi-label">未配送</div>
          <div className="kpi-value">{unservedCount}</div>
        </div>

        <div className="kpi kpi-active" title="总行驶距离（主目标或对比列）">
          <div className="kpi-label">总距离</div>
          <div className="kpi-value">
            {fmtNum(result.total_distance)}
            <span className="kpi-unit">km</span>
          </div>
        </div>

        <div className="kpi" title="总行驶时间（仅对比指标）">
          <div className="kpi-label">总时间</div>
          <div className="kpi-value">
            {fmtNum(result.total_travel_time)}
            <span className="kpi-unit">min</span>
          </div>
        </div>

        <div className="kpi kpi-serial" title="总运输成本">
          <div className="kpi-label">总成本</div>
          <div className="kpi-value">
            {fmtNum(result.total_cost)}
            <span className="kpi-unit">¥</span>
          </div>
        </div>

        <div
          className={`kpi ${result.is_feasible ? 'kpi-good' : 'kpi-bad'}`}
          title="可行性校验结果"
        >
          <div className="kpi-label">可行性</div>
          <div className="kpi-value" style={{ fontSize: 'var(--font-lg)' }}>
            {result.is_feasible ? '✓ 可行' : '✗ 不可行'}
          </div>
        </div>
      </div>

      {/* 方案概览 */}
      <details className="panel-section">
        <summary>方案与运行统计</summary>
        <ul className="status-list">
          <li>
            <span className="key">主目标</span>
            <span className="val">
              <span className="badge badge-info" style={{ fontSize: 10 }}>
                {obj}
              </span>
            </span>
          </li>
          <li>
            <span className="key">主目标值</span>
            <span className="val">{fmtNum(result.main_objective_total)} {obj === 'cost' ? '元' : 'km'}</span>
          </li>
          <li>
            <span className="key">车辆 ID</span>
            <span className="val">{result.vehicle_id}</span>
          </li>
          <li>
            <span className="key">仓库</span>
            <span className="val">{result.depot_id}</span>
          </li>
          <li>
            <span className="key">配送员</span>
            <span className="val">{result.courier_id ?? '—'}</span>
          </li>
          <li>
            <span className="key">规划耗时</span>
            <span className="val">{fmtNum(stats.runtime_seconds, 3)} s</span>
          </li>
          <li>
            <span className="key">Dijkstra 调用</span>
            <span className="val">{stats.dijkstra_calls}</span>
          </li>
          <li>
            <span className="key">缓存命中 / 未命中</span>
            <span className="val">
              {stats.cache_hits} / {stats.cache_misses}
            </span>
          </li>
          <li>
            <span className="key">可行性校验</span>
            <span className="val">{stats.feasibility_checks}</span>
          </li>
        </ul>
      </details>

      {/* 错误订单（如果有） */}
      {unservedCount > 0 && (
        <div className="panel-section">
          <div className="unserved-block">
            <strong>未配送订单（{unservedCount}）</strong>
            <ul>
              {result.unserved_orders.map((v) => (
                <li key={v.order_id}>
                  {v.order_id} — <em>{v.kind}</em>：{v.message}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <details className="panel-section" open>
        <summary>配送顺序 · {route.stop_sequence.length - 1} 段</summary>
        <p className="section-hint">点击站点与地图联动 · 到达 / 等待时间单位 min</p>
        <RouteTimeline stops={route.stops} stopSequence={route.stop_sequence} depotId={result.depot_id}
          activeNodeId={activeTimelineNodeId ?? null} onSelectNode={(id) => onSelectTimelineNode?.(id)} />
      </details>
      <details className="panel-section">
        <summary>路段详情 · {route.legs.length} 段</summary>
        <p className="section-hint">Dijkstra 实际路径 · 距离 km / 时间 min / 成本 元</p>
        <RouteLegDetails legs={route.legs} mainObjective={obj} />
      </details>
    </div>
  );
}
