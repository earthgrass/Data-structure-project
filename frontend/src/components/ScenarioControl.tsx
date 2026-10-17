// ScenarioControl —— 顶部场景控制 + 摘要。

import { useState } from 'react';
import type { ValidationReport } from '../types';

interface ScenarioControlProps {
  seed: number;
  onSeedChange: (s: number) => void;
  onGenerate: () => void;
  isGenerating: boolean;
  validation: ValidationReport | null;
  nodeCount: number;
  edgeCount: number;
  orderCount: number;
  vehicleCount: number;
  scenarioName: string | null;
}

export function ScenarioControl({
  seed,
  onSeedChange,
  onGenerate,
  isGenerating,
  validation,
  nodeCount,
  edgeCount,
  orderCount,
  vehicleCount,
  scenarioName,
}: ScenarioControlProps) {
  const [seedInput, setSeedInput] = useState(String(seed));

  return (
    <div className="topbar">
      <h1>LogiRoute Dashboard</h1>
      <span className="subtitle">单车辆电商物流配送路径规划系统 · Phase 5</span>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 24 }}>
        <label style={{ fontSize: 12, color: '#4a4f57' }}>seed:</label>
        <input
          type="number"
          value={seedInput}
          onChange={(e) => setSeedInput(e.target.value)}
          onBlur={() => {
            const n = parseInt(seedInput, 10);
            if (Number.isFinite(n)) onSeedChange(n);
          }}
          style={{ width: 80, padding: '4px 6px', border: '1px solid #d1d5db', borderRadius: 4 }}
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
        <span className="pill">名称：{scenarioName ?? '—'}</span>
        <span className="pill">节点 {nodeCount}</span>
        <span className="pill">边 {edgeCount}</span>
        <span className="pill">订单 {orderCount}</span>
        <span className="pill vehicle">车辆 {vehicleCount}（严格单车辆）</span>
        <span
          className="pill"
          style={{
            background: validation?.feasible ? '#d1fae5' : '#fee2e2',
            color: validation?.feasible ? '#065f46' : '#991b1b',
            fontWeight: 600,
          }}
        >
          独立 validator：{validation ? (validation.feasible ? 'feasible' : 'infeasible') : '—'}
        </span>
      </div>
    </div>
  );
}