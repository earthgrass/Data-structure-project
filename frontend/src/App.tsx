// App —— Phase 5 Dashboard 顶层组件。
// 状态管理：useState + useEffect；无第三方状态库。
// 防止 race condition：每次发起请求前用 requestId 标记；旧响应到达时若 requestId
// 已变更则丢弃，确保快速连续点击不会用旧场景的结果覆盖新结果。

import { useEffect, useRef, useState } from 'react';
import { ApiClientError, compareAlgorithms, generateRandomScenario, planDeliveries } from './api';
import { AlgorithmPanel } from './components/AlgorithmPanel';
import { ComparisonTable } from './components/ComparisonTable';
import { NetworkGraph } from './components/NetworkGraph';
import { ResultPanel } from './components/ResultPanel';
import { ScenarioControl } from './components/ScenarioControl';
import type {
  Algorithm,
  CompareResponse,
  Objective,
  PlanResponse,
  ScheduleResult,
  ScenarioResponse,
} from './types';

let REQUEST_ID = 0;

export function App() {
  const [seed, setSeed] = useState<number>(42);
  const [algorithm, setAlgorithm] = useState<Algorithm>('two_opt');
  const [objective, setObjective] = useState<Objective>('distance');

  const [scenarioResp, setScenarioResp] = useState<ScenarioResponse | null>(null);
  const [planResult, setPlanResult] = useState<PlanResponse | null>(null);
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null);

  const [isGenerating, setIsGenerating] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const requestRef = useRef<number>(0);

  useEffect(() => {
    // 进入页面时自动生成默认场景 —— 让用户立刻看到内容。
    void handleGenerate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleGenerate() {
    const id = ++REQUEST_ID;
    requestRef.current = id;
    setIsGenerating(true);
    setErrorMsg(null);
    // 清空旧结果 —— 场景切换必须作废旧数据
    setPlanResult(null);
    setCompareResult(null);
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
    setCompareResult(null); // 单算法调度 → 比较结果作废
    try {
      const resp = await planDeliveries(algorithm, objective);
      if (requestRef.current !== id) return;
      setPlanResult(resp);
    } catch (e) {
      if (requestRef.current !== id) return;
      setPlanResult(null);
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
    setPlanResult(null); // 比较结果会替代单算法结果
    try {
      const resp = await compareAlgorithms(objective);
      if (requestRef.current !== id) return;
      setCompareResult(resp);
    } catch (e) {
      if (requestRef.current !== id) return;
      setCompareResult(null);
      setErrorMsg(e instanceof ApiClientError ? `[${e.kind}] ${e.message}` : String(e));
    } finally {
      if (requestRef.current === id) setIsRunning(false);
    }
  }

  // 选择展示用的 result：plan 与 compare 互斥
  const displayedResult: ScheduleResult | null = planResult?.result ?? (
    compareResult?.results[algorithm] ?? null
  );

  const validation = scenarioResp?.validation ?? null;
  const scenario = scenarioResp?.scenario ?? null;

  return (
    <div className="app">
      <ScenarioControl
        seed={seed}
        onSeedChange={setSeed}
        onGenerate={handleGenerate}
        isGenerating={isGenerating}
        validation={validation}
        nodeCount={scenario?.graph.node_count ?? 0}
        edgeCount={scenario?.graph.edge_count ?? 0}
        orderCount={scenario?.orders.length ?? 0}
        vehicleCount={scenario?.vehicles.length ?? 0}
        scenarioName={scenario?.name ?? null}
      />

      {errorMsg && <div className="error-banner">{errorMsg}</div>}

      <AlgorithmPanel
        algorithm={algorithm}
        objective={objective}
        onAlgorithmChange={setAlgorithm}
        onObjectiveChange={setObjective}
        onPlan={handlePlan}
        onCompare={handleCompare}
        isRunning={isRunning}
        hasScenario={!!scenario}
      />

      <div className="center">
        <div className="legend">
          <span className="item">
            <span className="swatch" style={{ background: '#c2410c' }}></span>
            仓库
          </span>
          <span className="item">
            <span className="swatch" style={{ background: '#1e40af' }}></span>
            客户
          </span>
          <span className="item">
            <span className="swatch" style={{ background: '#6b7280' }}></span>
            中转站
          </span>
          <span className="item">
            <span style={{
              display: 'inline-block', width: 16, height: 2,
              background: '#c2410c', verticalAlign: 'middle',
            }}></span>
            当前配送路线
          </span>
        </div>
        <NetworkGraph
          graph={scenario?.graph ?? null}
          route={displayedResult?.route_plan ?? null}
        />
      </div>

      <ResultPanel
        result={displayedResult}
        emptyMessage={
          scenario
            ? '请选择算法后点击"运行规划"或"三算法比较"。'
            : '请先在左侧生成场景。'
        }
      />

      <ComparisonTable
        results={compareResult?.results ?? null}
        objective={compareResult?.objective ?? ''}
      />
    </div>
  );
}