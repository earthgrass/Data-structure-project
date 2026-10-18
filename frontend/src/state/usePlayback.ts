// Phase 5.3 —— usePlayback：客户端配送回放状态机。
//
// 与 AsyncState 解耦：playback 仅是 UI 表现，不参与任何业务计算；
// 不调用后端，不重跑 Dijkstra/TSP，路径顺序来自已有的 route_plan。
//
// 数据归属：
//   - OWN：自动/单段播放进度（stepIndex / legProgress / cumulative / 完成集）
//   - NOT OWN：不调用任何 API；不接受外部写
//   - DISPLAY：route 变化时自动 reset
//
// 严格单车辆约束：永远只有一个 vehicle marker（AGENTS §3.6）。
//
// Time   : O(legs) per tick（cumulative 重算 / 完成集重算）
// Space  : O(legs)（完成站点集合）

import { useEffect, useMemo, useRef, useState } from 'react';
import type { RoutePlanData } from '../types';

type PlaybackMode = 'auto' | 'manual';

export type PlaybackState =
  | { kind: 'idle' }
  | { kind: 'playing'; mode: PlaybackMode; stepIndex: number; legProgress: number }
  | { kind: 'paused'; stepIndex: number; legProgress: number }
  | { kind: 'done'; finishedAt: number };

export interface CumulativeMetrics {
  distance: number;
  time: number;
  cost: number;
}

export interface PlaybackView {
  state: PlaybackState;
  isPlaying: boolean;
  isPaused: boolean;
  isDone: boolean;
  currentLegIndex: number;          // -1 if not started, route.legs.length - 1 at final
  currentStopId: string | null;
  completedStops: ReadonlySet<string>;
  vehiclePosition: { path: string[]; t: number } | null;
  cumulative: CumulativeMetrics;
  progress: number;                  // 0..1
  nextSegment: { fromId: string; toId: string; index: number; total: number } | null;
}

const DEFAULT_SPEED_MS = 1800;
const TICK_MS = 60;
const MIN_ROAD_EDGE_MS = 600;

export interface UsePlaybackResult {
  view: PlaybackView;
  play: () => void;
  step: () => void;
  pause: () => void;
  reset: () => void;
}

export function usePlayback(
  route: RoutePlanData | null,
  speedMs: number = DEFAULT_SPEED_MS,
): UsePlaybackResult {
  const [state, setState] = useState<PlaybackState>({ kind: 'idle' });
  // 定时器读取最新路线；切换规划结果时重置，避免播放旧场景。
  const routeRef = useRef<RoutePlanData | null>(route);
  routeRef.current = route;

  useEffect(() => {
    setState({ kind: 'idle' });
  }, [route]);

  useEffect(() => {
    if (state.kind !== 'playing') return;
    const interval = window.setInterval(() => {
      const cur = routeRef.current;
      if (!cur) return;
      setState((prev) => {
        if (prev.kind !== 'playing') return prev;
        const roadEdges = Math.max(1, (cur.legs[prev.stepIndex]?.path.length ?? 1) - 1);
        const legDuration = Math.max(speedMs, roadEdges * MIN_ROAD_EDGE_MS);
        const nextProgress = prev.legProgress + TICK_MS / legDuration;
        if (nextProgress < 1) {
          return {
            ...prev,
            legProgress: Math.min(1, nextProgress),
          };
        }
        // 完成当前 leg → 进入下一 leg
        const nextIndex = prev.stepIndex + 1;
        if (nextIndex >= cur.legs.length) {
          return { kind: 'done', finishedAt: Date.now() };
        }
        if (prev.mode === 'manual') {
          // 单段播放到达下一配送站后停住，等待再次点击。
          return { kind: 'paused', stepIndex: nextIndex, legProgress: 0 };
        }
        return {
          kind: 'playing',
          mode: 'auto',
          stepIndex: nextIndex,
          legProgress: 0,
        };
      });
    }, TICK_MS);
    return () => window.clearInterval(interval);
  }, [state.kind, route, speedMs]);

  const start = (mode: PlaybackMode) => {
    const r = routeRef.current;
    if (!r || r.legs.length === 0 || state.kind === 'playing') return;
    const stepIndex = state.kind === 'paused' ? state.stepIndex : 0;
    const legProgress = state.kind === 'paused' ? state.legProgress : 0;
    setState({ kind: 'playing', mode, stepIndex, legProgress });
  };

  const pause = () => {
    setState((prev) => prev.kind === 'playing'
      ? { kind: 'paused', stepIndex: prev.stepIndex, legProgress: prev.legProgress }
      : prev);
  };

  const reset = () => setState({ kind: 'idle' });

  const view = useMemo<PlaybackView>(() => {
    const r = routeRef.current;
    const empty: PlaybackView = {
      state,
      isPlaying: state.kind === 'playing',
      isPaused: state.kind === 'paused',
      isDone: state.kind === 'done',
      currentLegIndex: -1,
      currentStopId: null,
      completedStops: new Set<string>(),
      vehiclePosition: null,
      cumulative: { distance: 0, time: 0, cost: 0 },
      progress: 0,
      nextSegment: null,
    };
    if (!r || r.legs.length === 0) return empty;
    if (state.kind === 'idle') {
      const first = r.legs[0];
      return { ...empty, nextSegment: {
        fromId: first.source, toId: first.target, index: 1, total: r.legs.length,
      } };
    }

    // stepIndex = 已完成 leg 数；legProgress = 当前 leg 内部进度
    const stepIndex = state.kind === 'done' ? r.legs.length : state.stepIndex;
    const legProgress = state.kind === 'done' ? 0 : state.legProgress;

    // completedStops：route.stop_sequence[0..stepIndex]（含起点）
    const completedStops = new Set<string>();
    for (let i = 0; i <= stepIndex && i < r.stop_sequence.length; i++) {
      completedStops.add(r.stop_sequence[i]);
    }

    // 车辆沿后端 leg.path 的道路节点序列移动，而非跨配送站直线移动。
    let vehiclePosition: PlaybackView['vehiclePosition'] = null;
    if ((state.kind === 'playing' || state.kind === 'paused') && stepIndex < r.legs.length) {
      const leg = r.legs[stepIndex];
      vehiclePosition = { path: leg.path, t: legProgress };
    } else if (state.kind === 'done' && r.legs.length > 0) {
      const last = r.legs[r.legs.length - 1];
      vehiclePosition = { path: last.path, t: 1 };
    }

    // cumulative：完整 leg 求和 + 当前 leg 部分
    let distance = 0;
    let time = 0;
    let cost = 0;
    for (let i = 0; i < stepIndex && i < r.legs.length; i++) {
      const cm = r.legs[i].cross_metrics ?? {};
      distance += cm.distance ?? 0;
      time += cm.travel_time ?? 0;
      cost += cm.cost ?? 0;
    }
    if (stepIndex < r.legs.length) {
      const cm = r.legs[stepIndex].cross_metrics ?? {};
      distance += (cm.distance ?? 0) * legProgress;
      time += (cm.travel_time ?? 0) * legProgress;
      cost += (cm.cost ?? 0) * legProgress;
    }

    // currentStopId
    let currentStopId: string | null = null;
    if (state.kind === 'playing' && stepIndex + 1 < r.stop_sequence.length) {
      currentStopId = r.stop_sequence[stepIndex + 1];
    } else if (state.kind === 'paused') {
      currentStopId = r.stop_sequence[stepIndex];
    } else if (state.kind === 'done') {
      currentStopId = r.stop_sequence[r.stop_sequence.length - 1];
    }

    // progress
    const totalLegs = r.legs.length;
    const progress = totalLegs === 0
      ? 0
      : Math.min(1, (stepIndex + legProgress) / totalLegs);

    return {
      state,
      isPlaying: state.kind === 'playing',
      isPaused: state.kind === 'paused',
      isDone: state.kind === 'done',
      currentLegIndex: stepIndex - 1,
      currentStopId,
      completedStops,
      vehiclePosition,
      cumulative: { distance, time, cost },
      progress,
      nextSegment: stepIndex < r.legs.length ? {
        fromId: r.legs[stepIndex].source,
        toId: r.legs[stepIndex].target,
        index: stepIndex + 1,
        total: r.legs.length,
      } : null,
    };
  }, [state, route]);

  return { view, play: () => start('auto'), step: () => start('manual'), pause, reset };
}
