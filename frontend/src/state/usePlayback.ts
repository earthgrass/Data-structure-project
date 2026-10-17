// Phase 5.3 —— usePlayback：客户端配送回放状态机。
//
// 与 AsyncState 解耦：playback 仅是 UI 表现，不参与任何业务计算；
// 不调用后端，不重跑 Dijkstra/CFI/2-opt，路径顺序来自已有的 route_plan。
//
// 数据归属：
//   - OWN：当前播放进度（stepIndex / legProgress / cumulative / 完成集）
//   - NOT OWN：不调用任何 API；不接受外部写
//   - DISPLAY：route 变化时自动 reset
//
// 严格单车辆约束：永远只有一个 vehicle marker（AGENTS §3.6）。
//
// Time   : O(legs) per tick（cumulative 重算 / 完成集重算）
// Space  : O(legs)（positions 缓存）

import { useEffect, useMemo, useRef, useState } from 'react';
import type { RoutePlanData } from '../types';

export type PlaybackState =
  | { kind: 'idle' }
  | { kind: 'playing'; startedAt: number; stepIndex: number; legProgress: number }
  | { kind: 'done'; finishedAt: number };

export interface CumulativeMetrics {
  distance: number;
  time: number;
  cost: number;
}

export interface PlaybackView {
  state: PlaybackState;
  isPlaying: boolean;
  isDone: boolean;
  currentLegIndex: number;          // -1 if not started, route.legs.length - 1 at final
  currentStopId: string | null;
  completedStops: ReadonlySet<string>;
  vehiclePosition: { fromId: string; toId: string; t: number } | null;
  cumulative: CumulativeMetrics;
  progress: number;                  // 0..1
}

const DEFAULT_SPEED_MS = 600;
const TICK_MS = 60;

export interface UsePlaybackResult {
  view: PlaybackView;
  play: () => void;
  reset: () => void;
}

export function usePlayback(
  route: RoutePlanData | null,
  speedMs: number = DEFAULT_SPEED_MS,
): UsePlaybackResult {
  const [state, setState] = useState<PlaybackState>({ kind: 'idle' });
  const intervalRef = useRef<number | null>(null);
  // 用 ref 保存 route，effect 内访问最新值，避免 stale closure
  const routeRef = useRef<RoutePlanData | null>(route);
  routeRef.current = route;

  // route 变化 → 自动 reset（不允许用旧 plan 播放新场景）
  useEffect(() => {
    if (intervalRef.current != null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setState({ kind: 'idle' });
  }, [route]);

  // 卸载清理
  useEffect(() => {
    return () => {
      if (intervalRef.current != null) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, []);

  const play = () => {
    const r = routeRef.current;
    if (!r || r.legs.length === 0) return;
    // 已 done → 从头重放；idle / playing → 维持当前进度
    if (state.kind === 'done') {
      setState({ kind: 'playing', startedAt: Date.now(), stepIndex: 0, legProgress: 0 });
    } else if (state.kind === 'idle') {
      setState({ kind: 'playing', startedAt: Date.now(), stepIndex: 0, legProgress: 0 });
    } else if (state.kind === 'playing') {
      // 重复点击 play：忽略（避免重置进度）
      return;
    }
    if (intervalRef.current != null) {
      window.clearInterval(intervalRef.current);
    }
    intervalRef.current = window.setInterval(() => {
      const cur = routeRef.current;
      if (!cur) {
        if (intervalRef.current != null) {
          window.clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        return;
      }
      setState((prev) => {
        if (prev.kind !== 'playing') return prev;
        const nextProgress = prev.legProgress + TICK_MS / speedMs;
        if (nextProgress < 1) {
          return {
            ...prev,
            legProgress: Math.min(1, nextProgress),
          };
        }
        // 完成当前 leg → 进入下一 leg
        const nextIndex = prev.stepIndex + 1;
        if (nextIndex >= cur.legs.length) {
          // 全部走完 → done
          if (intervalRef.current != null) {
            window.clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          return { kind: 'done', finishedAt: Date.now() };
        }
        return {
          kind: 'playing',
          startedAt: prev.startedAt,
          stepIndex: nextIndex,
          legProgress: 0,
        };
      });
    }, TICK_MS);
  };

  const reset = () => {
    if (intervalRef.current != null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setState({ kind: 'idle' });
  };

  const view = useMemo<PlaybackView>(() => {
    const r = routeRef.current;
    const empty: PlaybackView = {
      state,
      isPlaying: state.kind === 'playing',
      isDone: state.kind === 'done',
      currentLegIndex: -1,
      currentStopId: null,
      completedStops: new Set<string>(),
      vehiclePosition: null,
      cumulative: { distance: 0, time: 0, cost: 0 },
      progress: 0,
    };
    if (!r || r.legs.length === 0) return empty;
    if (state.kind === 'idle') return empty;

    // stepIndex = 已完成 leg 数；legProgress = 当前 leg 内部进度
    const stepIndex = state.kind === 'done' ? r.legs.length : state.stepIndex;
    const legProgress = state.kind === 'done' ? 1 : state.legProgress;

    // completedStops：route.stop_sequence[0..stepIndex]（含起点）
    const completedStops = new Set<string>();
    for (let i = 0; i <= stepIndex && i < r.stop_sequence.length; i++) {
      completedStops.add(r.stop_sequence[i]);
    }

    // vehicle position：当前 leg 的 (from, to) + t
    let vehiclePosition: PlaybackView['vehiclePosition'] = null;
    if (state.kind === 'playing' && stepIndex < r.legs.length) {
      const leg = r.legs[stepIndex];
      vehiclePosition = { fromId: leg.source, toId: leg.target, t: legProgress };
    } else if (state.kind === 'done' && r.legs.length > 0) {
      const last = r.legs[r.legs.length - 1];
      vehiclePosition = { fromId: last.source, toId: last.target, t: 1 };
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
      isDone: state.kind === 'done',
      currentLegIndex: stepIndex - 1,
      currentStopId,
      completedStops,
      vehiclePosition,
      cumulative: { distance, time, cost },
      progress,
    };
  }, [state, route]);

  return { view, play, reset };
}