// Phase 5 —— 左侧控制面板：目标选择 + 运行 + 比较。
// 不再出现 NN/CFI/2-opt 三选一；统一规划器内部走 CFI + 2-opt。

import type { Objective } from '../../types';

interface SidebarProps {
  objective: Objective;
  onObjectiveChange: (o: Objective) => void;
  onPlan: () => void;
  onCompare: () => void;
  isRunning: boolean;
  hasScenario: boolean;
}

const ALGO_PRINCIPLES = [
  '站点间路径由手写 Dijkstra 计算',
  '完整路线由 CFI（最低增量可行插入）构造',
  '受约束 2-opt 做有向图局部优化',
  '单车辆闭合回路；vehicle 由 lex-min 仓库选择',
];

export function Sidebar({
  objective,
  onObjectiveChange,
  onPlan,
  onCompare,
  isRunning,
  hasScenario,
}: SidebarProps) {
  return (
    <div className="panel sidebar">
      <h2>目标函数</h2>
      <div className="form-group">
        <label>主目标</label>
        <select
          value={objective}
          onChange={(e) => onObjectiveChange(e.target.value as Objective)}
          disabled={isRunning}
        >
          <option value="distance">最短距离</option>
          <option value="cost">最低运输成本</option>
        </select>
        <p style={{
          fontSize: 11, color: 'var(--text-muted)',
          margin: '4px 0 0', lineHeight: 1.4,
        }}>
          travel_time 作为结果中的对比指标展示（AGENTS §3.7：不允许作主目标）。
        </p>
      </div>

      <div className="btn-row">
        <button
          className="btn btn-primary"
          onClick={onPlan}
          disabled={!hasScenario || isRunning}
        >
          运行规划
        </button>
        <button
          className="btn"
          onClick={onCompare}
          disabled={!hasScenario || isRunning}
        >
          双目标比较
        </button>
      </div>

      {isRunning && (
        <div className="status-line running">调度计算中…</div>
      )}

      <h2 style={{ marginTop: 20 }}>算法原理</h2>
      <ul style={{
          margin: 0, paddingLeft: 16,
          fontSize: 12, color: 'var(--text-secondary)',
          lineHeight: 1.6,
        }}>
        {ALGO_PRINCIPLES.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
    </div>
  );
}