// Phase 5 验收整改 —— Sidebar：两卡片（目标函数 + 算法原理）。

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
  { name: 'Dijkstra', desc: '站点间路径权重计算' },
  { name: 'CFI', desc: '最低增量可行插入' },
  { name: '2-opt', desc: '有向图约束局部优化' },
  { name: '闭合回路', desc: 'depot → 全部客户 → depot' },
];

void ALGO_PRINCIPLES;  // referenced via JSX below

export function Sidebar({
  objective,
  onObjectiveChange,
  onPlan,
  onCompare,
  isRunning,
  hasScenario,
}: SidebarProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
      {/* 卡片 1：目标函数 */}
      <div className="card">
        <h3 className="card-title">
          <span>规划控制</span>
          <span className="icon" />
        </h3>

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
          <p className="form-hint">
            travel_time 作为结果对比指标展示，AGENTS §3.7 不允许作主目标。
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
            className="btn btn-secondary"
            onClick={onCompare}
            disabled={!hasScenario || isRunning}
          >
            双目标比较
          </button>
        </div>

        {isRunning && (
          <div className="status-line running">调度计算中…</div>
        )}
      </div>

      {/* 卡片 2：算法原理 */}
      <div className="card">
        <h3 className="card-title">
          <span>算法原理</span>
          <span
            className="icon"
            style={{ background: 'var(--identity-transfer)' }}
          />
        </h3>
        <ul className="algo-list">
          <li><code>Dijkstra</code>：站点间最优路径（手写 + 手写 MinHeap）</li>
          <li><code>CFI</code>：构造满足容量 / 时间窗的初始闭环</li>
          <li><code>2-opt</code>：有向图约束局部优化</li>
          <li>单车辆 + depot → 客户 → depot 闭合回路</li>
          <li>同场景可比较 distance / cost 两种目标</li>
        </ul>
      </div>
    </div>
  );
}