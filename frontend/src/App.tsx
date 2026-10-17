// Phase 5.2 —— Dashboard 顶层组件。
//
// 状态机（受 FinAgent-X V2 启发的工程实践）：
//
//   ┌─────────────────────────────────────────────────────────────────────┐
//   │  ScenarioState   AsyncState<ScenarioResponse>                        │
//   │  PlanState       AsyncState<PlanResponse>                           │
//   │  CompareState    AsyncState<CompareResponse>                         │
//   │  TimelineNode    string | null（地图 ↔ 时间轴联动）                  │
//   └─────────────────────────────────────────────────────────────────────┘
//
// 转换规则（强制）：
//   generate.seed=X
//     ├─ success  → scenario=success(X); plan=idle; compare=idle
//     ├─ error    → scenario=error(priorData=X?); plan=idle; compare=idle
//   plan(objective=Y)        → plan=loading; on success plan=success(Y);
//                               on error plan=error（scenario/compare 不变）
//   compare()                → compare=loading; on success compare=success;
//                               on error / 不完整 compare=error
//   （详细「数据归属」见 docs/DASHBOARD_STATE_MODEL.md）
//
// 不变量：
//   - 后端是唯一数据源；前端不做任何业务计算（AGENTS §1）。
//   - 错误请求不会伪装成功：error 态不显示 success.data。
//   - scenario error 但存在 previousData 时，UI 显示「stale」徽章 + 错误横幅，
//     不冒充为新场景。
//   - race condition 防护：每个 in-flight 请求有递增 id，迟到的 settle/fail
//     不会覆盖更新的状态。

import { useEffect, useRef, useState } from 'react';
import {
  ApiClientError,
  compareObjectives,
  generateRandomScenario,
  planDeliveries,
} from './api';
import { HeaderBar } from './components/layout/HeaderBar';
import { SideNav } from './components/layout/SideNav';
import { NetworkMap } from './components/map/NetworkMap';
import { ResultPanel } from './components/results/ResultPanel';
import { ObjectiveComparison } from './components/results/ObjectiveComparison';
import { useAsyncResource, displayData } from './state/useAsyncState';
import type {
  CompareResponse,
  Objective,
  PlanResponse,
  ScenarioResponse,
} from './types';

import './styles/tokens.css';
import './styles/global.css';
import './styles/dashboard.css';

export function App() {
  const [seed, setSeed] = useState<number>(42);
  const [objective, setObjective] = useState<Objective>('distance');

  const scenario = useAsyncResource<ScenarioResponse>();
  const plan = useAsyncResource<PlanResponse>();
  const compare = useAsyncResource<CompareResponse>();

  const [activeTimelineNodeId, setActiveTimelineNodeId] = useState<string | null>(null);

  // race-condition 跟踪：每个 handler 自带 request id，迟到的响应被丢弃
  const inFlightRef = useRef<{ generate?: number; plan?: number; compare?: number }>({});

  // 首次挂载自动生成 seed=42
  useEffect(() => {
    void handleGenerate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleGenerate() {
    const id = scenario.start();
    inFlightRef.current.generate = id;
    // 关键转换：scenario 进入 loading 时，强制清空 plan / compare 与联动节点
    plan.reset();
    compare.reset();
    setActiveTimelineNodeId(null);
    try {
      const resp = await generateRandomScenario({ seed });
      if (inFlightRef.current.generate !== id) return;
      scenario.settle(resp);
    } catch (e) {
      if (inFlightRef.current.generate !== id) return;
      // 错误态会保留 previousData（来自 settle 之前的 success.data）
      scenario.fail(toApiError(e));
      plan.reset();
      compare.reset();
    }
  }

  async function handlePlan() {
    const id = plan.start();
    inFlightRef.current.plan = id;
    // plan 操作不动 scenario，但清空时间轴联动（节点可能在旧 plan 中）
    setActiveTimelineNodeId(null);
    try {
      const resp = await planDeliveries(objective);
      if (inFlightRef.current.plan !== id) return;
      plan.settle(resp);
    } catch (e) {
      if (inFlightRef.current.plan !== id) return;
      plan.fail(toApiError(e));
    }
  }

  async function handleCompare() {
    const id = compare.start();
    inFlightRef.current.compare = id;
    setActiveTimelineNodeId(null);
    try {
      const resp = await compareObjectives(true, true);
      if (inFlightRef.current.compare !== id) return;
      // 完整性校验：必须两个目标都返回才能视为成功
      const objectives = resp.objectives ?? [];
      if (objectives.length < 2 || !resp.results['distance'] || !resp.results['cost']) {
        compare.fail(
          new ApiClientError(
            `双目标结果不完整（仅 ${objectives.length} 个目标），无法对比`,
            200,
            'incomplete_compare',
          ),
        );
      } else {
        compare.settle(resp);
      }
    } catch (e) {
      if (inFlightRef.current.compare !== id) return;
      compare.fail(toApiError(e));
    }
  }

  // 派生数据：使用 displayData 让 loading / error 期间也能显示最近一次
  // 成功的数据，避免「点击生成 → 顶部统计短暂变 0 → 重新填入」的视觉闪烁。
  // success 态 isStale=false；loading/error 携带 previousData 时 isStale=true。
  const scenarioView = displayData(scenario.state);
  const scenarioData = scenarioView.data;
  const scenarioIsStale = scenarioView.isStale || (scenario.state.kind === 'error' && scenario.data !== null);

  const planResult = plan.fresh?.result ?? null;
  const compareData = compare.fresh ?? null;

  return (
    <div className="dashboard-shell">
      {/* —— 全局错误横幅：scenario 与 plan / compare 三处错误分别渲染 —— */}
      {scenario.state.kind === 'error' && !scenario.data && (
        <ScenarioErrorBanner
          error={scenario.state.error}
          onRetry={handleGenerate}
          onDismiss={() => scenario.reset()}
        />
      )}
      {scenario.state.kind === 'error' && scenario.data && (
        <ScenarioStaleBanner
          error={scenario.state.error}
          loadedSeed={scenario.data.scenario.random_seed}
          requestedSeed={seed}
          onRetry={handleGenerate}
        />
      )}
      {plan.state.kind === 'error' && (
        <PlanErrorBanner
          error={plan.state.error}
          onRetry={handlePlan}
          onDismiss={() => plan.reset()}
        />
      )}
      {compare.state.kind === 'error' && (
        <CompareErrorBanner
          error={compare.state.error}
          onRetry={handleCompare}
          onDismiss={() => compare.reset()}
        />
      )}

      <div className="app">
        <HeaderBar
          validation={scenarioData?.validation ?? null}
          scenarioName={scenarioData?.scenario.name ?? null}
          nodeCount={scenarioData?.scenario.graph.node_count ?? 0}
          edgeCount={scenarioData?.scenario.graph.edge_count ?? 0}
          orderCount={scenarioData?.scenario.orders.length ?? 0}
          vehicleCount={scenarioData?.scenario.vehicles.length ?? 0}
          scenarioIsStale={scenarioIsStale}
        />

        <SideNav
          seed={seed}
          onSeedChange={setSeed}
          onGenerate={handleGenerate}
          isGenerating={scenario.loading}
          objective={objective}
          onObjectiveChange={setObjective}
          onPlan={handlePlan}
          onCompare={handleCompare}
          isRunning={plan.loading || compare.loading}
          hasScenario={!!scenarioData}
          scenarioName={scenarioData?.scenario.name ?? null}
          nodeCount={scenarioData?.scenario.graph.node_count ?? 0}
          edgeCount={scenarioData?.scenario.graph.edge_count ?? 0}
          orderCount={scenarioData?.scenario.orders.length ?? 0}
          vehicleCount={scenarioData?.scenario.vehicles.length ?? 0}
          validation={scenarioData?.validation ?? null}
          scenarioIsStale={scenarioIsStale}
        />

        <div className="center">
          <NetworkMap
            graph={scenarioData?.scenario.graph ?? null}
            route={planResult?.route_plan ?? null}
            validation={scenarioData?.validation ?? null}
            scenarioName={scenarioData?.scenario.name ?? null}
            resultSummary={planResult}
            activeTimelineNodeId={activeTimelineNodeId}
            onNodeHover={setActiveTimelineNodeId}
          />
        </div>

        <ResultPanel
          result={planResult}
          objective={
            plan.fresh?.objective === 'distance' || plan.fresh?.objective === 'cost'
              ? plan.fresh.objective
              : null
          }
          hasScenario={!!scenarioData}
          activeTimelineNodeId={activeTimelineNodeId}
          onSelectTimelineNode={setActiveTimelineNodeId}
          errorMessage={
            plan.state.kind === 'error' ? errorMessageOf(plan.state.error) : null
          }
          onRetry={plan.state.kind === 'error' ? handlePlan : undefined}
        />

        <ObjectiveComparison
          data={compareData}
          scenarioName={scenarioData?.scenario.name ?? null}
          errorMessage={
            compare.state.kind === 'error' ? errorMessageOf(compare.state.error) : null
          }
        />
      </div>
    </div>
  );
}

// ============================================================================
//  小型错误横幅组件（保持单一职责；可被 ErrorState 复用）
// ============================================================================

function ScenarioErrorBanner({
  error,
  onRetry,
  onDismiss,
}: {
  error: ApiClientError | Error;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  return (
    <GlobalErrorBanner
      title="场景生成失败"
      message={errorMessageOf(error)}
      recovery={recoveryOf(error)}
      onRetry={onRetry}
      onDismiss={onDismiss}
    />
  );
}

function ScenarioStaleBanner({
  error,
  loadedSeed,
  requestedSeed,
  onRetry,
}: {
  error: ApiClientError | Error;
  loadedSeed: number;
  requestedSeed: number;
  onRetry: () => void;
}) {
  return (
    <GlobalErrorBanner
      title={`新场景（seed=${requestedSeed}）生成失败，仍展示 seed=${loadedSeed} 的旧场景`}
      message={errorMessageOf(error)}
      recovery={recoveryOf(error)}
      onRetry={onRetry}
      severity="stale"
    />
  );
}

function PlanErrorBanner({
  error,
  onRetry,
  onDismiss,
}: {
  error: ApiClientError | Error;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  return (
    <GlobalErrorBanner
      title="规划失败"
      message={errorMessageOf(error)}
      recovery={recoveryOf(error)}
      onRetry={onRetry}
      onDismiss={onDismiss}
    />
  );
}

function CompareErrorBanner({
  error,
  onRetry,
  onDismiss,
}: {
  error: ApiClientError | Error;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  return (
    <GlobalErrorBanner
      title="双目标比较失败"
      message={errorMessageOf(error)}
      recovery={recoveryOf(error)}
      onRetry={onRetry}
      onDismiss={onDismiss}
    />
  );
}

function GlobalErrorBanner({
  title,
  message,
  recovery,
  onRetry,
  onDismiss,
  severity = 'critical',
}: {
  title: string;
  message: string;
  recovery?: string | null;
  onRetry: () => void;
  onDismiss?: () => void;
  severity?: 'critical' | 'stale';
}) {
  return (
    <div className={`global-error-banner severity-${severity}`} role="alert">
      <div className="geb-text">
        <div className="geb-title">⚠ {title}</div>
        <div className="geb-message">{message}</div>
        {recovery && <div className="geb-recovery">{recovery}</div>}
      </div>
      <div className="geb-actions">
        <button className="btn btn-secondary" onClick={onRetry}>
          重试
        </button>
        {onDismiss && (
          <button
            className="btn btn-ghost"
            onClick={onDismiss}
            aria-label="关闭错误横幅"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

// ============================================================================
//  工具函数
// ============================================================================

function toApiError(e: unknown): ApiClientError | Error {
  if (e instanceof ApiClientError) return e;
  if (e instanceof Error) return e;
  return new Error(String(e));
}

function errorMessageOf(e: ApiClientError | Error): string {
  if (e instanceof ApiClientError) {
    return e.message ? `[${e.kind}] ${e.message}` : `[${e.kind}]`;
  }
  return e.message || '未知错误';
}

function recoveryOf(e: ApiClientError | Error): string | null {
  if (e instanceof ApiClientError && e.recovery) return e.recovery;
  return null;
}
