// Phase 5 —— 前端 API 客户端。
// 所有调用都基于 fetch（浏览器原生），不引入 axios / ky。
// 返回值统一：成功时返回 T；后端 4xx/5xx 时抛 ApiClientError（前端统一捕获并显示）。

import type {
  Algorithm,
  CompareResponse,
  HealthResponse,
  Objective,
  PlanResponse,
  ScenarioResponse,
} from './types';

const BASE = ''; // 同源；Vite proxy 转发到 127.0.0.1:8000。

export class ApiClientError extends Error {
  status: number;
  kind: string;
  details?: Record<string, unknown>;

  constructor(message: string, status: number, kind: string, details?: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.kind = kind;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  const text = await resp.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { raw: text };
  }
  if (!resp.ok) {
    const errBody = body as { error?: { kind: string; message: string; details?: Record<string, unknown> } } | null;
    const kind = errBody?.error?.kind ?? 'http_error';
    const message = errBody?.error?.message ?? `HTTP ${resp.status}`;
    throw new ApiClientError(message, resp.status, kind, errBody?.error?.details);
  }
  return body as T;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health');
}

export interface RandomScenarioParams {
  seed: number;
  orders_count?: number;
  capacity?: number;
}

export async function generateRandomScenario(
  params: RandomScenarioParams,
): Promise<ScenarioResponse> {
  return request<ScenarioResponse>('/api/scenario/random', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function fetchCurrentScenario(): Promise<ScenarioResponse> {
  return request<ScenarioResponse>('/api/scenario/current');
}

export async function planDeliveries(
  algorithm: Algorithm,
  objective: Objective,
): Promise<PlanResponse> {
  return request<PlanResponse>('/api/plan', {
    method: 'POST',
    body: JSON.stringify({ algorithm, objective }),
  });
}

export async function compareAlgorithms(
  objective: Objective,
  algorithms?: Algorithm[],
): Promise<CompareResponse> {
  return request<CompareResponse>('/api/compare', {
    method: 'POST',
    body: JSON.stringify({ objective, algorithms }),
  });
}