// Phase 5.3 —— SideNav：左侧分组导航（参考 FinAgent-X V2 工程实践）。
//
// 三段结构：规划 / 数据 / 算法 + 底部品牌脚注。
//
// 数据归属：
//   - OWN：seed 输入、目标 chip、播放控件（playback 控制）
//   - NOT OWN：不调用任何 API；所有交互经 props 回调到 App.tsx 顶层
//   - DISPLAY：仅展示 props 传入的数据
//   - 严禁 mock / 硬编码 KPI 或伪造成功状态
//
// 严格单车辆约束：在「数据」组底部固定显示「已锁定」徽章（AGENTS §3.6）。

import type { Objective, ValidationReport } from '../../types';
import type { PlaybackView } from '../../state/usePlayback';

interface SideNavProps {
  // —— 规划组 ——
  seed: number;
  onSeedChange: (s: number) => void;
  onGenerate: () => void;
  isGenerating: boolean;
  objective: Objective;
  onObjectiveChange: (o: Objective) => void;
  onPlan: () => void;
  onCompare: () => void;
  isRunning: boolean;
  hasScenario: boolean;
  hasPlan: boolean;
  playback: PlaybackView;
  onPlay: () => void;
  onReset: () => void;

  // —— 数据组 ——
  scenarioName: string | null;
  nodeCount: number;
  edgeCount: number;
  orderCount: number;
  vehicleCount: number;
  validation: ValidationReport | null;
  scenarioIsStale?: boolean;
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

export function SideNav({
  seed,
  onSeedChange,
  onGenerate,
  isGenerating,
  objective,
  onObjectiveChange,
  onPlan,
  onCompare,
  isRunning,
  hasScenario,
  hasPlan,
  playback,
  onPlay,
  onReset,
  scenarioName,
  nodeCount,
  edgeCount,
  orderCount,
  vehicleCount,
  validation,
  scenarioIsStale = false,
}: SideNavProps) {
  return (
    <aside className="sidenav" role="navigation" aria-label="左侧导航">
      <div className="sidenav-stack">
        {/* ===== 组 1：规划 ===== */}
        <section className="sidenav-group" aria-label="规划">
          <div className="sidenav-group-title">
            <span>规划</span>
            <span className="sidenav-group-dot" aria-hidden />
          </div>

          <div className="sidenav-row sidenav-row-control">
            <label htmlFor="sidenav-seed-input" className="sidenav-row-label">
              SEED
            </label>
            <div className="seed-input sidenav-seed-input">
              <input
                id="sidenav-seed-input"
                type="number"
                value={seed}
                onChange={(e) => {
                  const n = parseInt(e.target.value, 10);
                  if (Number.isFinite(n)) onSeedChange(n);
                }}
                aria-label="随机场景种子"
              />
            </div>
          </div>

          <button
            className="btn btn-accent sidenav-row sidenav-row-primary"
            onClick={onGenerate}
            disabled={isGenerating || isRunning}
          >
            {isGenerating ? '生成中…' : '随机生成场景'}
          </button>

          <div className="sidenav-row sidenav-row-control">
            <span className="sidenav-row-label">主目标</span>
            <div className="sidenav-chip-row" role="radiogroup" aria-label="主目标">
              <button
                type="button"
                className={`sidenav-chip ${objective === 'distance' ? 'is-active' : ''}`}
                onClick={() => onObjectiveChange('distance')}
                disabled={isRunning || !hasScenario}
                role="radio"
                aria-checked={objective === 'distance'}
              >
                最短距离
              </button>
              <button
                type="button"
                className={`sidenav-chip ${objective === 'cost' ? 'is-active' : ''}`}
                onClick={() => onObjectiveChange('cost')}
                disabled={isRunning || !hasScenario}
                role="radio"
                aria-checked={objective === 'cost'}
              >
                最低成本
              </button>
            </div>
          </div>

          <button
            className="btn btn-primary sidenav-row sidenav-row-primary"
            onClick={onPlan}
            disabled={!hasScenario || isRunning}
          >
            {isRunning ? '计算中…' : '运行规划'}
          </button>
          <button
            className="btn btn-secondary sidenav-row"
            onClick={onCompare}
            disabled={!hasScenario || isRunning}
          >
            双目标比较
          </button>

          <div className="sidenav-divider" aria-hidden />

          <button
            className="btn btn-accent sidenav-row sidenav-row-primary"
            onClick={onPlay}
            disabled={!hasPlan || playback.isPlaying}
          >
            {playback.isPlaying
              ? '播放中…'
              : playback.isDone
                ? '重播配送过程'
                : '▶ 播放配送过程'}
          </button>
          {(playback.isPlaying || playback.isDone) && (
            <button
              className="btn btn-ghost sidenav-row sidenav-row-secondary"
              onClick={onReset}
            >
              重置
            </button>
          )}

          {isRunning && (
            <div className="status-line running sidenav-status">调度计算中…</div>
          )}
        </section>

        {/* ===== 组 2：数据 ===== */}
        <section className="sidenav-group" aria-label="数据">
          <div className="sidenav-group-title">
            <span>数据</span>
            <span className="sidenav-group-dot" aria-hidden />
          </div>

          <div className="sidenav-row sidenav-row-meta">
            <div className="sidenav-row-meta-key">场景</div>
            <div className="sidenav-row-meta-val">
              {scenarioName ?? '—'}
              <span
                className={`badge sidenav-row-badge ${
                  scenarioName ? 'badge-real' : 'badge-na'
                }`}
              >
                <span className="dot" />
                {scenarioName ? 'REAL' : 'NA'}
              </span>
            </div>
          </div>

          {scenarioIsStale && (
            <div className="sidenav-row sidenav-row-stale">
              <span className="badge badge-warn">
                <span className="dot" />
                旧场景（stale）
              </span>
            </div>
          )}

          <div className="sidenav-row sidenav-row-meta">
            <div className="sidenav-row-meta-key">节点</div>
            <div className="sidenav-row-meta-val">
              {nodeCount}
              <span
                className={`badge sidenav-row-badge ${
                  nodeCount > 0 ? 'badge-real' : 'badge-na'
                }`}
              >
                <span className="dot" />
                {nodeCount > 0 ? 'REAL' : 'NA'}
              </span>
            </div>
          </div>
          <div className="sidenav-row sidenav-row-meta">
            <div className="sidenav-row-meta-key">边</div>
            <div className="sidenav-row-meta-val">
              {edgeCount}
              <span
                className={`badge sidenav-row-badge ${
                  edgeCount > 0 ? 'badge-real' : 'badge-na'
                }`}
              >
                <span className="dot" />
                {edgeCount > 0 ? 'REAL' : 'NA'}
              </span>
            </div>
          </div>
          <div className="sidenav-row sidenav-row-meta">
            <div className="sidenav-row-meta-key">订单</div>
            <div className="sidenav-row-meta-val">
              {orderCount}
              <span
                className={`badge sidenav-row-badge ${
                  orderCount > 0 ? 'badge-real' : 'badge-na'
                }`}
              >
                <span className="dot" />
                {orderCount > 0 ? 'REAL' : 'NA'}
              </span>
            </div>
          </div>
          <div className="sidenav-row sidenav-row-meta">
            <div className="sidenav-row-meta-key">车辆</div>
            <div className="sidenav-row-meta-val">
              {vehicleCount}
              <span
                className={`badge sidenav-row-badge badge-info sidenav-row-badge-lock`}
                title="严格单车辆硬约束（AGENTS §3.6）"
              >
                <span className="dot" />
                已锁定
              </span>
            </div>
          </div>

          {validation && (
            <div className="sidenav-row sidenav-row-meta">
              <div className="sidenav-row-meta-key">校验</div>
              <div className="sidenav-row-meta-val">
                <span
                  className={`badge sidenav-row-badge ${
                    validation.feasible ? 'badge-real' : 'badge-na'
                  }`}
                  title="独立 validator 七项校验"
                >
                  <span className="dot" />
                  {validation.feasible ? 'PASS' : 'FAIL'}
                </span>
              </div>
            </div>
          )}
        </section>

        {/* ===== 组 3：算法 ===== */}
        <section className="sidenav-group sidenav-group-scroll" aria-label="算法">
          <div className="sidenav-group-title">
            <span>算法</span>
            <span className="sidenav-group-dot" aria-hidden />
          </div>

          <ul className="algo-list sidenav-algo-list">
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
        </section>

        {/* ===== 脚注 ===== */}
        <div className="sidenav-footer">
          <div className="sidenav-footer-mark">LogiRoute</div>
          <div className="sidenav-footer-sub">
            Phase 5.3 · 单车辆物流调度
          </div>
        </div>
      </div>
    </aside>
  );
}