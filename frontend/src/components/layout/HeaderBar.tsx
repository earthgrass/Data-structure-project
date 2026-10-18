import type { ValidationReport } from '../../types';

interface HeaderBarProps {
  scenarioName: string | null;
  validation: ValidationReport | null;
  nodeCount: number;
  edgeCount: number;
  orderCount: number;
  vehicleCount: number;
  /** 当前显示的场景是否是 stale（旧场景因新生成失败而保留） */
  scenarioIsStale?: boolean;
}

export function HeaderBar({ scenarioName, validation, nodeCount, edgeCount, orderCount,
  vehicleCount, scenarioIsStale = false }: HeaderBarProps) {
  return (
    <header className="topbar">
      <div className="brand"><span className="brand-mark" aria-hidden>↗</span>
        <div><strong>LogiRoute</strong><span className="subtitle">智能物流 · 单车配送调度</span></div>
      </div>
      <div className="summary" aria-label="场景状态摘要">
        <span className="header-scenario mono" title={scenarioName ?? undefined}>{scenarioName ?? '等待场景'}</span>
        <span>节点 <b>{scenarioName ? nodeCount : '—'}</b></span>
        <span>有向边 <b>{scenarioName ? edgeCount : '—'}</b></span>
        <span>订单 <b>{scenarioName ? orderCount : '—'}</b></span>
        <span>车辆 <b>{scenarioName ? vehicleCount : '—'}</b></span>
        <span className={`badge ${scenarioIsStale ? 'badge-warn' : validation?.feasible ? 'badge-feasible' : validation ? 'badge-infeasible' : 'badge-neutral'}`}>
          {scenarioIsStale ? '保留旧场景' : validation ? (validation.feasible ? '校验通过' : '校验失败') : '等待校验'}
        </span>
      </div>
    </header>
  );
}
