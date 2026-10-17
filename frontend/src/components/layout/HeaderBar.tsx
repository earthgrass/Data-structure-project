// Phase 5.3 —— HeaderBar：精简型全局顶栏。
// 3 段结构：品牌区 / 自适应占位 / 状态徽章区（场景摘要 + 数据时间 + 数据源状态）。
//
// 重构说明：
//   * seed 输入与「随机生成场景」按钮已迁移到 SideNav「规划」组；
//   * 数据源状态（REAL/NA）由 scenarioName 派生，1s 刷新本地时钟；
//   * validator 状态已迁移到 SideNav「数据」组，避免重复。
//
// 数据归属：
//   - OWN：实时时钟（无外部依赖）
//   - NOT OWN：不调用任何 API；所有数据由父组件 props 注入
//   - DISPLAY：受控展示

import { useEffect, useState } from 'react';
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

function formatClock(d: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function HeaderBar({
  scenarioName,
  validation,
  nodeCount,
  edgeCount,
  orderCount,
  vehicleCount,
  scenarioIsStale = false,
}: HeaderBarProps) {
  const [now, setNow] = useState<Date>(() => new Date());

  // 1 秒一次本地时钟刷新（仅用于显示，不参与任何业务计算）
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const hasData = !!scenarioName;

  return (
    <div className="topbar" role="banner">
      {/* 品牌区 */}
      <div className="brand">
        <span className="brand-mark" aria-hidden />
        <div>
          <h1>LogiRoute</h1>
          <span className="subtitle">单车辆物流配送调度工作台 · Phase 5.3</span>
        </div>
      </div>

      {/* 占位列 */}
      <div />

      {/* 状态徽章区 */}
      <div className="summary" aria-label="场景状态摘要">
        <span className="badge badge-neutral" title="场景名称">
          {scenarioName ?? '—'}
        </span>
        {scenarioIsStale && (
          <span
            className="badge badge-warn"
            title="当前显示的是旧场景（因新场景生成失败而保留）"
          >
            <span className="dot" />
            旧场景（stale）
          </span>
        )}
        <span className="badge badge-neutral" title="节点数">
          <span className="dot" />
          节点 {nodeCount}
        </span>
        <span className="badge badge-neutral" title="边数">
          <span className="dot" />
          边 {edgeCount}
        </span>
        <span className="badge badge-neutral" title="订单数">
          <span className="dot" />
          订单 {orderCount}
        </span>
        <span
          className="badge badge-vehicle"
          title="严格单车辆约束"
        >
          <span className="dot" />
          车辆 {vehicleCount}（单车辆）
        </span>
        {validation && (
          <span
            className={`badge ${validation.feasible ? 'badge-feasible' : 'badge-infeasible'}`}
            title="独立 validator 七项校验结果"
          >
            <span className="dot" />
            validator：{validation.feasible ? 'PASS' : 'FAIL'}
          </span>
        )}
        <span
          className={`badge ${hasData ? 'badge-real' : 'badge-na'}`}
          title="数据源加载状态"
        >
          <span className="dot" />
          数据源：{hasData ? 'REAL' : 'NA'}
        </span>
        <span className="badge badge-neutral" title="本地时钟">
          <span className="dot" />
          数据时间 {formatClock(now)}
        </span>
      </div>
    </div>
  );
}