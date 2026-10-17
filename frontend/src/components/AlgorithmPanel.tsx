// AlgorithmPanel —— 左侧算法选择 + 主目标 + 操作按钮。

import type { Algorithm, Objective } from '../types';

interface AlgorithmPanelProps {
  algorithm: Algorithm;
  objective: Objective;
  onAlgorithmChange: (a: Algorithm) => void;
  onObjectiveChange: (o: Objective) => void;
  onPlan: () => void;
  onCompare: () => void;
  isRunning: boolean;
  hasScenario: boolean;
}

export function AlgorithmPanel({
  algorithm,
  objective,
  onAlgorithmChange,
  onObjectiveChange,
  onPlan,
  onCompare,
  isRunning,
  hasScenario,
}: AlgorithmPanelProps) {
  return (
    <div className="panel sidebar">
      <h2>算法与目标</h2>

      <div className="form-group">
        <label>算法</label>
        <select
          value={algorithm}
          onChange={(e) => onAlgorithmChange(e.target.value as Algorithm)}
          disabled={isRunning}
        >
          <option value="nearest_neighbor">最近邻（NN）</option>
          <option value="insertion">可行插入（CFI）</option>
          <option value="two_opt">受约束 2-opt</option>
        </select>
      </div>

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
        <p style={{ fontSize: 11, color: '#6c7079', margin: '4px 0 0' }}>
          行驶时间作为结果中的对比指标展示（AGENTS §3.7：不允许作主目标）。
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
          三算法比较
        </button>
      </div>

      {isRunning && (
        <div className="algorithm-status running">调度计算中…</div>
      )}
    </div>
  );
}