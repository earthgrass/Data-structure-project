// Phase 5 —— 顶部场景信息条：seed 输入 + 随机生成 + 当前场景摘要。

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
      <span className="subtitle">北京区域物流配送规划 · Phase 5</span>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <label style={{ fontSize: 12, color: 'var(--text-secondary)' }}>seed</label>
        <input
          type="number"
          defaultValue={seed}
          onBlur={(e) => {
            const n = parseInt(e.target.value, 10);
            if (Number.isFinite(n) && n !== seed) onSeedChange(n);
          }}
          style={{
            width: 80, padding: '4px 6px',
            border: '1px solid var(--border-default)',
            borderRadius: 4, fontSize: 13,
          }}
        />
        <button
          className="btn btn-primary"
          onClick={onGenerate}
          disabled={isGenerating}
        >
          {isGenerating ? '生成中…' : '随机生成场景'}
        </button>
      </div>

      <div className="summary">
        <span className="pill">{scenarioName ?? '—'}</span>
        <span className="pill">节点 {nodeCount}</span>
        <span className="pill">边 {edgeCount}</span>
        <span className="pill">订单 {orderCount}</span>
        <span className="pill vehicle">
          车辆 {vehicleCount}（严格单车辆）
        </span>
        {validation && (
          <span className={`pill ${validation.feasible ? 'feasible' : 'infeasible'}`}>
            validator：{validation.feasible ? 'feasible' : 'infeasible'}
          </span>
        )}
      </div>
    </div>
  );
}