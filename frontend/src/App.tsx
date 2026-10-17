// Phase 5.2 —— Dashboard 顶层组件（修复布局：全局错误横幅移到 grid 之外）。
// 状态机：场景生成 → 调度计算 → 比较；防 race condition 用 requestRef。
// 跨组件联动：时间轴 ↔ 地图节点高亮。
//
// 布局层级：
//   .dashboard-shell
//     .global-error-banner          ← 仅在 globalError 时显示
//     .app                          ← 5 层 grid（topbar / sidebar+center+result / comparison）
//       HeaderBar
//       Sidebar
//       .center > NetworkMap
//       ResultPanel
//       ObjectiveComparison

import { useEffect, useRef, useState } from 'react';
import {
  ApiClientError,
  compareObjectives,
  generateRandomScenario,
  planDeliveries,
} from './api';
import { HeaderBar } from './components/layout/HeaderBar';
import { Sidebar } from './components/planning/Sidebar';
import { NetworkMap } from './components/map/NetworkMap';
import { ResultPanel } from './components/results/ResultPanel';
import { ObjectiveComparison } from './components/results/ObjectiveComparison';
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
  const [planError, setPlanError] = useState<string | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [globalErrorRecovery, setGlobalErrorRecovery] = useState<string | null>(null);

  // 时间轴 ↔ 地图联动
  const [activeTimelineNodeId, setActiveTimelineNodeId] = useState<string | null>(null);

  const requestRef = useRef<number>(0);

  // 首次挂载自动生成 seed=42
  useEffect(() => {
    void handleGenerate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setGlobalErrorFromApi(e: unknown, fallback: string) {
    if (e instanceof ApiClientError) {
      setGlobalError(`[${e.kind}] ${e.message || fallback}`);
      setGlobalErrorRecovery(e.recovery ?? null);
    } else {
      setGlobalError(fallback);
      setGlobalErrorRecovery(null);
    }
  }

  async function handleGenerate() {
    const id = ++REQUEST_ID;
    requestRef.current = id;
    setIsGenerating(true);
    setPlanError(null);
    setCompareError(null);
    setGlobalError(null);
    setGlobalErrorRecovery(null);
    setPlanResp(null);
    setCompareResp(null);
    setActiveTimelineNodeId(null);
    try {
      const resp = await generateRandomScenario({ seed });
      if (requestRef.current !== id) return;
      setScenarioResp(resp);
    } catch (e) {
      if (requestRef.current !== id) return;
      setScenarioResp(null);
      setGlobalErrorFromApi(e, '场景生成失败');
    } finally {
      if (requestRef.current === id) setIsGenerating(false);
    }
  }

  async function handlePlan() {
    const id = ++REQUEST_ID;
    requestRef.current = id;
    setIsRunning(true);
    setPlanError(null);
    setCompareError(null);
    setActiveTimelineNodeId(null);
    try {
      const resp = await planDeliveries(objective);
      if (requestRef.current !== id) return;
      setPlanResp(resp);
    } catch (e) {
      if (requestRef.current !== id) return;
      setPlanResp(null);
      setPlanError(
        e instanceof ApiClientError ? `[${e.kind}] ${e.message}` : String(e),
      );
    } finally {
      if (requestRef.current === id) setIsRunning(false);
    }
  }

  async function handleCompare() {
    const id = ++REQUEST_ID;
    requestRef.current = id;
    setIsRunning(true);
    setPlanError(null);
    setCompareError(null);
    setPlanResp(null);
    setActiveTimelineNodeId(null);
    try {
      const resp = await compareObjectives(true, true);
      if (requestRef.current !== id) return;
      const objectives = resp.objectives ?? [];
      if (objectives.length < 2 || !resp.results['distance'] || !resp.results['cost']) {
        setCompareResp(null);
        setCompareError(
          `双目标结果不完整（仅 ${objectives.length} 个目标），无法对比`,
        );
      } else {
        setCompareResp(resp);
      }
    } catch (e) {
      if (requestRef.current !== id) return;
      setCompareResp(null);
      setCompareError(
        e instanceof ApiClientError ? `[${e.kind}] ${e.message}` : String(e),
      );
    } finally {
      if (requestRef.current === id) setIsRunning(false);
    }
  }

  const displayedResult = planResp?.result ?? null;
  const validation = scenarioResp?.validation ?? null;
  const scenario = scenarioResp?.scenario ?? null;
  const hasScenario = !!scenario;

  return (
    <div className="dashboard-shell">
      {globalError && (
        <div className="global-error-banner" role="alert">
          <div className="geb-text">
            <div className="geb-title">⚠ 场景生成失败</div>
            <div className="geb-message">{globalError}</div>
            {globalErrorRecovery && (
              <div className="geb-recovery">{globalErrorRecovery}</div>
            )}
          </div>
          <div className="geb-actions">
            <button
              className="btn btn-secondary"
              onClick={() => void handleGenerate()}
              disabled={isGenerating}
            >
              {isGenerating ? '重试中…' : '重试'}
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => {
                setGlobalError(null);
                setGlobalErrorRecovery(null);
              }}
              aria-label="关闭错误横幅"
            >
              ✕
            </button>
          </div>
        </div>
      )}

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

        <Sidebar
          scenarioName={scenario?.name ?? null}
          nodeCount={scenario?.graph.node_count ?? 0}
          edgeCount={scenario?.graph.edge_count ?? 0}
          orderCount={scenario?.orders.length ?? 0}
          vehicleCount={scenario?.vehicles.length ?? 0}
          seed={seed}
          isGenerating={isGenerating}
          onGenerate={handleGenerate}
          objective={objective}
          onObjectiveChange={setObjective}
          onPlan={handlePlan}
          onCompare={handleCompare}
          isRunning={isRunning}
          hasScenario={hasScenario}
        />

        <div className="center">
          <NetworkMap
            graph={scenario?.graph ?? null}
            route={displayedResult?.route_plan ?? null}
            validation={validation}
            scenarioName={scenario?.name ?? null}
            resultSummary={displayedResult}
            activeTimelineNodeId={activeTimelineNodeId}
            onNodeHover={setActiveTimelineNodeId}
          />
        </div>

        <ResultPanel
          result={displayedResult}
          objective={
            planResp?.objective === 'distance' || planResp?.objective === 'cost'
              ? planResp.objective
              : null
          }
          hasScenario={hasScenario}
          activeTimelineNodeId={activeTimelineNodeId}
          onSelectTimelineNode={setActiveTimelineNodeId}
          errorMessage={planError}
          onRetry={planError ? handlePlan : undefined}
        />

        <ObjectiveComparison
          data={compareResp}
          scenarioName={scenario?.name ?? null}
          errorMessage={compareError}
        />
      </div>
    </div>
  );
}
