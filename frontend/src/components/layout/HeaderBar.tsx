// Phase 5.1 —— HeaderBar：紧凑型全局顶栏。
// 4 段结构：品牌区 / 控制区（seed + 生成） / 自适应占位 / 状态徽章区。

import type { ValidationReport } from '../../types';

interface HeaderBarProps {
  seed: number;
  onSeedChange: (s: number) => void;
  onGenerate: () => void;
  isGenerating: boolean;
  validation: ValidationReport | null;
  scenarioName: string | null;
  nodeCount: number;
  edgeCount: number;
  orderCount: number;
  vehicleCount: number;
}

export function HeaderBar({
  seed,
  onSeedChange,
  onGenerate,
  isGenerating,
  validation,
  scenarioName,
  nodeCount,
  edgeCount,
  orderCount,
  vehicleCount,
}: HeaderBarProps) {
  return (
    <div className="topbar" role="banner">
      {/* 品牌区 */}
      <div className="brand">
        <span className="brand-mark" aria-hidden />
        <div>
          <h1>LogiRoute</h1>
          <span className="subtitle">单车辆物流配送调度工作台 · Phase 5.1</span>
        </div>
      </div>

      {/* 控制区：seed + 生成 */}
      <div className="control-cluster">
        <div className="seed-input">
          <label htmlFor="seed-input">SEED</label>
          <input
            id="seed-input"
            type="number"
            defaultValue={seed}
            onBlur={(e) => {
              const n = parseInt(e.target.value, 10);
              if (Number.isFinite(n) && n !== seed) onSeedChange(n);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                (e.target as HTMLInputElement).blur();
              }
            }}
            aria-label="随机场景种子"
          />
        </div>
        <button
          className="btn btn-primary"
          onClick={onGenerate}
          disabled={isGenerating}
        >
          {isGenerating ? '生成中…' : '随机生成场景'}
        </button>
      </div>

      {/* 占位列 */}
      <div />

      {/* 状态徽章区 */}
      <div className="summary" aria-label="场景状态摘要">
        <span className="badge badge-neutral" title="场景名称">
          {scenarioName ?? '—'}
        </span>
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
      </div>
    </div>
  );
}
