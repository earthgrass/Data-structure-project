// Phase 5 验收整改 —— HeaderBar（更专业的 badge 风格）。

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
    <div className="topbar">
      <h1>LogiRoute</h1>
      <span className="subtitle">北京区域物流配送规划系统 · Phase 5</span>

      <div className="seed-input">
        <label>seed</label>
        <input
          type="number"
          defaultValue={seed}
          onBlur={(e) => {
            const n = parseInt(e.target.value, 10);
            if (Number.isFinite(n) && n !== seed) onSeedChange(n);
          }}
        />
      </div>

      <button
        className="btn btn-primary"
        onClick={onGenerate}
        disabled={isGenerating}
      >
        {isGenerating ? '生成中…' : '随机生成场景'}
      </button>

      <div className="summary">
        <span className="badge badge-neutral">{scenarioName ?? '—'}</span>
        <span className="badge badge-neutral">
          <span className="dot" /> 节点 {nodeCount}
        </span>
        <span className="badge badge-neutral">
          <span className="dot" /> 边 {edgeCount}
        </span>
        <span className="badge badge-neutral">
          <span className="dot" /> 订单 {orderCount}
        </span>
        <span className="badge badge-vehicle">
          <span className="dot" /> 车辆 {vehicleCount}（严格单车辆）
        </span>
        {validation && (
          <span className={`badge ${validation.feasible ? 'badge-feasible' : 'badge-infeasible'}`}>
            <span className="dot" />
            validator：{validation.feasible ? 'PASS' : 'FAIL'}
          </span>
        )}
      </div>
    </div>
  );
}