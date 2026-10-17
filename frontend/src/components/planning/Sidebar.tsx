// Phase 5.1 —— Sidebar：3 卡片布局。
// A. 场景控制（操作所需） / B. 目标函数控制（运行规划） / C. 算法说明。

import type { Objective } from '../../types';

interface SidebarProps {
  scenarioName: string | null;
  nodeCount: number;
  edgeCount: number;
  orderCount: number;
  vehicleCount: number;
  seed: number;
  isGenerating: boolean;
  onGenerate: () => void;
  objective: Objective;
  onObjectiveChange: (o: Objective) => void;
  onPlan: () => void;
  onCompare: () => void;
  isRunning: boolean;
  hasScenario: boolean;
}

const ALGO_STEPS = [
  {
    name: '手写 Dijkstra',
    desc: '站点之间的有向最短路径由手写 MinHeap + Dijkstra 计算。',
  },
  {
    name: 'CFI 初始闭环',
    desc: 'Cheapest Feasible Insertion 构造满足容量 / 时间窗的初始路线。',
  },
  {
    name: '受约束 2-opt',
    desc: '在有向图 + 单车辆约束下做局部搜索改进。',
  },
  {
    name: '单车辆闭合回路',
    desc: '一辆车从仓库出发，访问所有待配送点后返回仓库。',
  },
  {
    name: 'distance / cost 双目标',
    desc: '两种主目标在同一场景快照下可并行对比；travel_time 仅作对比列。',
  },
];

export function Sidebar({
  scenarioName,
  nodeCount,
  edgeCount,
  orderCount,
  vehicleCount,
  seed,
  isGenerating,
  onGenerate,
  objective,
  onObjectiveChange,
  onPlan,
  onCompare,
  isRunning,
  hasScenario,
}: SidebarProps) {
  return (
    <div className="sidebar-stack">
      {/* ===== 卡片 A：场景控制 ===== */}
      <div className="card" aria-label="场景控制">
        <h3 className="card-title">
          <span>场景控制</span>
          <span className="icon-pill warehouse" title="场景">W</span>
        </h3>

        <div className="form-group">
          <label>当前场景</label>
          <div
            style={{
              fontSize: 'var(--font-sm)',
              color: 'var(--text-primary)',
              fontWeight: 600,
              padding: '6px 0',
            }}
          >
            {scenarioName ?? '未加载'}
          </div>
        </div>

        <div className="form-group">
          <label>当前 seed</label>
          <div
            style={{
              fontSize: 'var(--font-sm)',
              color: 'var(--text-secondary)',
              fontVariantNumeric: 'tabular-nums',
              padding: '6px 0',
            }}
          >
            {seed}
          </div>
        </div>

        <ul className="status-list">
          <li>
            <span className="key">节点</span>
            <span className="val">{nodeCount}</span>
          </li>
          <li>
            <span className="key">边</span>
            <span className="val">{edgeCount}</span>
          </li>
          <li>
            <span className="key">订单</span>
            <span className="val">{orderCount}</span>
          </li>
          <li>
            <span className="key">车辆（严格单车辆）</span>
            <span className="val">{vehicleCount}</span>
          </li>
        </ul>

        <div className="btn-row">
          <button
            className="btn btn-secondary"
            onClick={onGenerate}
            disabled={isGenerating || isRunning}
          >
            {isGenerating ? '生成中…' : '随机生成场景'}
          </button>
        </div>
      </div>

      {/* ===== 卡片 B：目标函数控制 ===== */}
      <div className="card" aria-label="目标函数控制">
        <h3 className="card-title">
          <span>目标函数</span>
          <span className="icon-pill customer" title="目标">C</span>
        </h3>

        <div className="form-group">
          <label>主目标</label>
          <select
            value={objective}
            onChange={(e) => onObjectiveChange(e.target.value as Objective)}
            disabled={isRunning || !hasScenario}
          >
            <option value="distance">最短距离</option>
            <option value="cost">最低运输成本</option>
          </select>
          <p className="form-hint">
            travel_time 仅作为对比指标展示；本系统授权范围内不允许作为主目标
            （AGENTS.md §3.6 / §3.7）。
          </p>
        </div>

        <div className="btn-row">
          <button
            className="btn btn-primary"
            onClick={onPlan}
            disabled={!hasScenario || isRunning}
          >
            {isRunning ? '计算中…' : '运行规划'}
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

      {/* ===== 卡片 C：算法说明 ===== */}
      <div className="card card-scroll" aria-label="算法说明">
        <h3 className="card-title">
          <span>算法说明</span>
          <span className="icon-pill transfer" title="算法">T</span>
        </h3>

        <ul className="algo-list">
          {ALGO_STEPS.map((s, i) => (
            <li className="algo-step" key={`algo-${i}`}>
              <span className="step-num">{i + 1}</span>
              <span className="step-text">
                <strong>{s.name}</strong>
                <span>{s.desc}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
