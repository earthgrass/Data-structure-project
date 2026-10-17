// Phase 5 —— Dashboard 顶层组件（统一规划器 / 双目标）。
// 状态机：场景生成 → 调度计算 → 比较；防 race condition 用 requestId。

import { useEffect, useRef, useState } from 'react';
import { ApiClientError, compareObjectives, generateRandomScenario, planDeliveries } from './api';
import { HeaderBar } from './components/layout/HeaderBar';
import { Sidebar } from './components/planning/Sidebar';
import { BeijingMap } from './components/BeijingMap';
import { ObjectiveComparison } from './components/results/ObjectiveComparison';
import { ResultPanel } from './components/results/ResultPanel';
import type {
  CompareResponse,
  Objective,
  PlanResponse,
  ScenarioResponse,
} from './types';

import './styles/tokens.css';
import './styles/global.css';
import './styles/dashboard.css';

let REQUEST_ID = 0;

export function App() {
  const [seed, setSeed] = useState<number>(42);
  const [objective, setObjective] = useState<Objective>('distance');

  const [scenarioResp, setScenarioResp] = useState<ScenarioResponse | null>(null);
  const [planResp, setPlanResp] = useState<PlanResponse | null>(null);
  const [compareResp, setCompareResp] = useState<CompareResponse | null>(null);

  const [isGenerating, setIsGenerating] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const requestRef = useRef<number>(0);

  useEffect(() => {
    void handleGenerate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleGenerate() {
    const id = ++REQUEST_ID;
    requestRef.current = id;
    setIsGenerating(true);
    setErrorMsg(null);
    setPlanResp(null);
    setCompareResp(null);
    try {
      const resp = await generateRandomScenario({ seed });
      if (requestRef.current !== id) return;
      setScenarioResp(resp);
    } catch (e) {
      if (requestRef.current !== id) return;
      setScenarioResp(null);
      setErrorMsg(e instanceof ApiClientError ? `[${e.kind}] ${e.message}` : String(e));
    } finally {
      if (requestRef.current === id) setIsGenerating(false);
    }
  }

  async function handlePlan() {
    const id = ++REQUEST_ID;
    requestRef.current = id;
    setIsRunning(true);
    setErrorMsg(null);
    setCompareResp(null);
    try {
      const resp = await planDeliveries(objective);
      if (requestRef.current !== id) return;
      setPlanResp(resp);
    } catch (e) {
      if (requestRef.current !== id) return;
      setPlanResp(null);
      setErrorMsg(e instanceof ApiClientError ? `[${e.kind}] ${e.message}` : String(e));
    } finally {
      if (requestRef.current === id) setIsRunning(false);
    }
  }

  async function handleCompare() {
    const id = ++REQUEST_ID;
    requestRef.current = id;
    setIsRunning(true);
    setErrorMsg(null);
    setPlanResp(null);
    try {
      const resp = await compareObjectives(true, true);
      if (requestRef.current !== id) return;
      setCompareResp(resp);
    } catch (e) {
      if (requestRef.current !== id) return;
      setCompareResp(null);
      setErrorMsg(e instanceof ApiClientError ? `[${e.kind}] ${e.message}` : String(e));
    } finally {
      if (requestRef.current === id) setIsRunning(false);
    }
  }

  // display 结果：plan 与 compare 互斥；plan 默认显示当前 objective 对应结果
  const displayedResult = planResp?.result ?? null;

  const validation = scenarioResp?.validation ?? null;
  const scenario = scenarioResp?.scenario ?? null;

  return (
    <div className="app">
      <HeaderBar
        seed={seed}
        onSeedChange={setSeed}
        onGenerate={handleGenerate}
        isGenerating={isGenerating}
        validation={validation}
        scenarioName={scenario?.name ?? null}
        nodeCount={scenario?.graph.node_count ?? 0}
        edgeCount={scenario?.graph.edge_count ?? 0}
        orderCount={scenario?.orders.length ?? 0}
        vehicleCount={scenario?.vehicles.length ?? 0}
      />

      {errorMsg && <div className="error-banner">{errorMsg}</div>}

      <Sidebar
        objective={objective}
        onObjectiveChange={setObjective}
        onPlan={handlePlan}
        onCompare={handleCompare}
        isRunning={isRunning}
        hasScenario={!!scenario}
      />

      <div className="center">
        <div className="map-legend">
          <span className="legend-item">
            <svg width="12" height="12">
              <rect x="2" y="2" width="8" height="8" fill="var(--identity-warehouse)" />
            </svg>
            仓库
          </span>
          <span className="legend-item">
            <svg width="12" height="12">
              <circle cx="6" cy="6" r="5" fill="var(--identity-customer)" />
            </svg>
            客户
          </span>
          <span className="legend-item">
            <svg width="12" height="12">
              <polygon points="6,1 11,10 1,10" fill="var(--identity-transfer)" />
            </svg>
            中转
          </span>
          <span className="legend-item">
            <svg width="14" height="2">
              <rect y="0" width="14" height="2" fill="var(--identity-route-active)" />
            </svg>
            当前配送路线
          </span>
          <span className="legend-item">
            <svg width="14" height="2">
              <rect y="0" width="14" height="2" fill="var(--identity-route-edge)" opacity="0.55" />
            </svg>
            非路线边
          </span>
        </div>
        <BeijingMap
          graph={scenario?.graph ?? null}
          route={displayedResult?.route_plan ?? null}
        />
        <div className="disclaimer">
          本系统以北京区域为示意场景；物流网络及其权重为系统生成的课程设计数据，不代表真实道路导航结果。
        </div>
      </div>

      <ResultPanel
        result={displayedResult}
        objective={planResp?.objective ?? null}
        emptyMessage={
          scenario
            ? '请选择目标后点击「运行规划」或「双目标比较」。'
            : '请先在左侧生成场景。'
        }
      />

      <ObjectiveComparison data={compareResp} />
    </div>
  );
}