// Phase 5.2 —— 通用 AsyncState 状态机（受 FinAgent-X V2 启发的工程实践）。
//
// 设计原则（来自 FinAgent-X V2 / LogiRoute Phase 5.2 任务书）：
//   1. 后端 API 是唯一真实数据源；前端不持有任何独立副本
//   2. 每个 UI 资源（场景 / 规划 / 比较）有显式的 4 种状态
//   3. 失败时显式记录 attemptedAt 与 previousData，便于显示「保留旧场景」
//   4. 不允许「上一次成功数据被冒充为最新」——UI 必须能区分 stale vs fresh
//
// 借鉴 FinAgent-X run-context：单一状态机 + 显式转换；不模仿其 SSE/polling。

import { useCallback, useRef, useState } from 'react';
import { ApiClientError } from '../api';

/**
 * 异步资源的标准 4 态：
 *   - idle:    尚未加载（初始或重置后）
 *   - loading: 请求在飞行中
 *   - success: 最近一次请求成功（带 loadedAt 时间戳，便于 stale 判断）
 *   - error:   最近一次请求失败（带 attemptedAt 与可选的 previousData）
 *
 * 任何「保留旧数据」逻辑必须显式从 error.previousData 读取，
 * 不得与 success.data 混淆。
 */
export type AsyncState<T> =
  | { readonly kind: 'idle' }
  | {
      readonly kind: 'loading';
      readonly startedAt: number;
      /** 进入 loading 之前已成功的旧数据；失败时作为 previousData 兜底 */
      readonly previousData?: T;
    }
  | {
      readonly kind: 'success';
      readonly data: T;
      readonly loadedAt: number;
    }
  | {
      readonly kind: 'error';
      readonly error: ApiClientError | Error;
      readonly attemptedAt: number;
      readonly previousData?: T;
    };

/** 便捷构造函数 */
export const idle = <T,>(): AsyncState<T> => ({ kind: 'idle' });
export const loading = <T,>(
  startedAt = Date.now(),
  previousData?: T,
): AsyncState<T> => ({
  kind: 'loading',
  startedAt,
  previousData,
});
export const success = <T,>(data: T, loadedAt = Date.now()): AsyncState<T> => ({
  kind: 'success',
  data,
  loadedAt,
});
export const failure = <T,>(
  error: ApiClientError | Error,
  attemptedAt = Date.now(),
  previousData?: T,
): AsyncState<T> => ({
  kind: 'error',
  error,
  attemptedAt,
  previousData,
});

/** 类型守卫 */
export function isLoading<T>(s: AsyncState<T>): boolean {
  return s.kind === 'loading';
}
export function isSuccess<T>(s: AsyncState<T>): s is Extract<AsyncState<T>, { kind: 'success' }> {
  return s.kind === 'success';
}
export function isError<T>(s: AsyncState<T>): s is Extract<AsyncState<T>, { kind: 'error' }> {
  return s.kind === 'error';
}
export function hasData<T>(s: AsyncState<T>): s is Extract<AsyncState<T>, { kind: 'success' } | { kind: 'error'; previousData: T }> {
  return s.kind === 'success' || (s.kind === 'error' && s.previousData !== undefined);
}

/**
 * useAsyncResource — 围绕单一异步资源的最小状态机。
 *
 * 关键不变量：
 *   - start / settle 不会变更 stale closure（使用 ref 跟踪 inFlight id）
 *   - 失败时若 caller 传入 priorData，会自动写入 previousData 字段
 *   - reset 会把状态回到 idle（用于「明确放弃旧数据」场景）
 */
export interface AsyncResource<T> {
  state: AsyncState<T>;
  /** 当前是否处于加载态 */
  loading: boolean;
  /** 当前是否成功且未被错误覆盖 */
  fresh: T | null;
  /** 当前可用的数据（含 stale previousData）—— 用于「保留旧场景」语义 */
  data: T | null;
  /** 当前是否处于错误态 */
  error: ApiClientError | Error | null;
  /** 触发加载；返回的资源必须经 settle() 确认才会更新 state */
  start: () => number;
  /** 请求成功 */
  settle: (data: T) => void;
  /** 请求失败；priorData 用于保留旧数据 */
  fail: (err: ApiClientError | Error, priorData?: T) => void;
  /** 重置为 idle（不保留旧数据） */
  reset: () => void;
}

export function useAsyncResource<T>(): AsyncResource<T> {
  const [state, setState] = useState<AsyncState<T>>(idle<T>());
  const inFlightRef = useRef<number>(0);

  const start = useCallback((): number => {
    const id = ++inFlightRef.current;
    // 进入 loading；若当前态是 success，则把其 data 透传至 loading.previousData，
    // 失败时 fail() 会沿用，避免「保留旧场景」语义丢失。
    setState((prev) => {
      const previousData =
        prev.kind === 'success'
          ? prev.data
          : prev.kind === 'loading'
          ? prev.previousData
          : prev.kind === 'error'
          ? prev.previousData
          : undefined;
      return loading<T>(Date.now(), previousData);
    });
    return id;
  }, []);

  const settle = useCallback((data: T) => {
    setState(success(data, Date.now()));
    inFlightRef.current++;
  }, []);

  const fail = useCallback((err: ApiClientError | Error, priorData?: T) => {
    setState((prev) => {
      const previousData =
        priorData !== undefined
          ? priorData
          : prev.kind === 'success'
          ? prev.data
          : prev.kind === 'error'
          ? prev.previousData
          : prev.kind === 'loading'
          ? prev.previousData
          : undefined;
      return failure<T>(err, Date.now(), previousData);
    });
    inFlightRef.current++;
  }, []);

  const reset = useCallback(() => {
    setState(idle<T>());
    inFlightRef.current++;
  }, []);

  return {
    state,
    loading: state.kind === 'loading',
    fresh: state.kind === 'success' ? state.data : null,
    data:
      state.kind === 'success'
        ? state.data
        : state.kind === 'error' && state.previousData !== undefined
        ? state.previousData
        : null,
    error: state.kind === 'error' ? state.error : null,
    start,
    settle,
    fail,
    reset,
  };
}

/** 过期判定（毫秒）。超过该时间认为 success.data 已陈旧，仅作为参考。 */
export function isStaleByAge<T>(
  s: AsyncState<T>,
  maxAgeMs: number,
  now = Date.now(),
): boolean {
  if (s.kind !== 'success') return false;
  return now - s.loadedAt > maxAgeMs;
}

/**
 * displayData —— 在 loading / error 状态下都能拿到「最近一次成功的数据」，
 * 供 UI 在过渡期间不闪烁（避免「点击生成 → 顶部统计短暂变 0」的视觉异常）。
 *
 * 返回值是只读的视图；不允许修改。
 *
 * 注意：与 state machine 的语义不同 —— displayData 只是渲染辅助，
 * 真正的「成功」判定仍依赖 state.kind === 'success'。
 */
export function displayData<T>(
  s: AsyncState<T>,
): { data: T | null; isStale: boolean } {
  if (s.kind === 'success') return { data: s.data, isStale: false };
  if (s.kind === 'loading' && s.previousData !== undefined) {
    return { data: s.previousData, isStale: true };
  }
  if (s.kind === 'error' && s.previousData !== undefined) {
    return { data: s.previousData, isStale: true };
  }
  return { data: null, isStale: false };
}
