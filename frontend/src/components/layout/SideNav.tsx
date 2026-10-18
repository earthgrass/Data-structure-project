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
  sourceLabel: string;
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
    name: 'Dijkstra 距离矩阵',
    desc: '在完整路网上运行手写单源 Dijkstra，形成仓库与订单点的有向最短路矩阵。',
  },
  {
    name: '有向 TSP 搜索',
    desc: '在距离矩阵上搜索访问顺序，逐步检查容量与时间窗。',
  },
  {
    name: '有界状态保留',
    desc: '手写最大堆保留较优候选；束宽截断时不保证全局最优。',
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
  sourceLabel,
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
  const busy = isGenerating || isRunning;
  return (
    <aside className="sidenav" aria-label="规划控制">
      <div className="sidenav-stack">
        <div className="sidenav-heading"><span className="eyebrow">PLANNING CONSOLE</span><h2>规划控制台</h2><p>配置场景，生成单车配送闭环。</p></div>
        <section className="sidenav-group" aria-label="场景控制">
          <h3>01 <span>场景控制</span></h3>
          <label className="sidenav-row-label" htmlFor="sidenav-seed-input">随机种子 Seed</label>
          <input id="sidenav-seed-input" type="number" value={seed} disabled={busy} aria-label="随机场景种子"
            onChange={(e) => { const n = Number(e.target.value); if (Number.isSafeInteger(n)) onSeedChange(n); }} />
          <button className="btn btn-secondary" onClick={onGenerate} disabled={busy}>{isGenerating ? '生成中…' : '↻ 随机生成场景'}</button>
          <p className="sidenav-caption">相同种子可复现相同场景。</p>
        </section>
        <section className="sidenav-group" aria-label="规划目标与操作">
          <h3>02 <span>规划目标</span></h3>
          <div className="sidenav-chip-row" aria-label="主目标">
            {(['distance', 'cost'] as const).map((o) => <button key={o} type="button" className={`sidenav-chip ${objective === o ? 'is-active' : ''}`}
              aria-pressed={objective === o} disabled={busy || !hasScenario} onClick={() => onObjectiveChange(o)}>{o === 'distance' ? '最短距离' : '最低成本'}</button>)}
          </div>
          <button className="btn btn-primary" onClick={onPlan} disabled={!hasScenario || busy}>{isRunning ? '计算中…' : '运行规划 →'}</button>
          <button className="btn btn-secondary" onClick={onCompare} disabled={!hasScenario || busy}>双目标比较</button>
          <button className="btn btn-ghost" onClick={onPlay} disabled={!hasPlan || busy || playback.isPlaying}>{playback.isPlaying ? '播放中…' : playback.isDone ? '重播配送过程' : '▷ 播放配送过程'}</button>
          {(playback.isPlaying || playback.isDone) && <button className="btn btn-ghost" onClick={onReset}>重置回放</button>}
        </section>
        <section className="sidenav-group" aria-label="场景数据">
          <h3>03 <span>场景数据</span></h3>
          <div className="sidenav-caption mono">{scenarioName ?? '尚未加载场景'}</div>
          {scenarioIsStale && <span className="badge badge-warn">保留旧场景</span>}
          <dl className="sidebar-stats">
            <div><dt>节点 / 有向边</dt><dd>{hasScenario ? `${nodeCount} / ${edgeCount}` : '—'}</dd></div>
            <div><dt>订单 / 车辆</dt><dd>{hasScenario ? `${orderCount} / ${vehicleCount}` : '—'}</dd></div>
            <div><dt>Validator</dt><dd>{validation ? (validation.feasible ? 'PASS' : 'FAIL') : '—'}</dd></div>
          </dl>
          <p className="sidenav-caption">{sourceLabel} · 示意坐标</p>
          {validation && !validation.feasible && <ul className="validation-errors">{validation.violations.map((v, i) => <li key={i}>{v.message}</li>)}</ul>}
        </section>
        <details className="sidenav-group algorithm-help"><summary>算法与约束说明</summary>
          <ul className="algo-list">{ALGO_STEPS.map((s) => <li key={s.name}><strong>{s.name}</strong><p>{s.desc}</p></li>)}</ul>
          <p>启发式规划，不保证全局最优。不可行订单将保留原因。</p>
        </details>
      </div>
    </aside>
  );
}
