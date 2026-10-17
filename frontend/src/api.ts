// Phase 5 —— 前端 API 客户端（统一接口：algorithm 字段已弃用）。
// 错误分类：
//   - network_error：fetch 本身失败（后端未启动 / CORS / 离线）
//   - proxy_error：Vite 代理返回 500/502/503/504 但 body 为空（典型：后端进程挂了）
//   - http_error：后端返回非 2xx，但 body 不符合统一错误格式
//   - server_error：后端返回 APIError 标准体（{error: {kind, message}}）

import type {
  CompareResponse,
  HealthResponse,
  Objective,
  PlanResponse,
  ScenarioResponse,
} from './types';

const BASE = '';

export class ApiClientError extends Error {
  status: number;
  kind: string;
  details?: Record<string, unknown>;
  /** 完整恢复建议（用户可读）；用于全局错误横幅 */
  recovery?: string;

  constructor(
    message: string,
    status: number,
    kind: string,
    details?: Record<string, unknown>,
    recovery?: string,
  ) {
    super(message);
    this.status = status;
    this.kind = kind;
    this.details = details;
    this.recovery = recovery;
  }
}

interface ErrorBody {
  error?: { kind: string; message: string; details?: Record<string, unknown> };
}

const BACKEND_DOWN_RECOVERY =
  '后端服务不可达。请在项目根目录运行：PYTHONPATH=src python -m uvicorn logiroute.api:app --host 127.0.0.1 --port 8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    });
  } catch (e) {
    // fetch 本身失败（连接被拒 / 离线 / DNS）
    throw new ApiClientError(
      `网络错误：${(e as Error).message ?? '无法连接到后端服务'}`,
      0,
      'network_error',
      undefined,
      BACKEND_DOWN_RECOVERY,
    );
  }

  const text = await resp.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { raw: text };
  }

  if (!resp.ok) {
    const errBody = body as ErrorBody | null;
    const hasStructured = !!errBody?.error?.message;
    if (!hasStructured) {
      // 典型：Vite 代理在 backend down 时返回 500 但 body 为空
      const isProxyError =
        resp.status >= 500 && (!text || text.trim() === '');
      const recovery = isProxyError
        ? BACKEND_DOWN_RECOVERY
        : `后端返回 HTTP ${resp.status}，但响应体不是标准 JSON 错误格式`;
      throw new ApiClientError(
        isProxyError
          ? 'Vite 代理未能连接后端服务'
          : `HTTP ${resp.status}（响应体格式异常）`,
        resp.status,
        isProxyError ? 'proxy_error' : 'http_error',
        undefined,
        recovery,
      );
    }
    const kind = errBody!.error!.kind;
    const message = errBody!.error!.message;
    throw new ApiClientError(
      message,
      resp.status,
      kind,
      errBody!.error!.details,
      '检查后端日志；如反复出现可重启 uvicorn。',
    );
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
  objective: Objective,
): Promise<PlanResponse> {
  return request<PlanResponse>('/api/plan', {
    method: 'POST',
    body: JSON.stringify({ objective }),
  });
}

export async function compareObjectives(
  distance: boolean = true,
  cost: boolean = true,
): Promise<CompareResponse> {
  return request<CompareResponse>('/api/compare', {
    method: 'POST',
    body: JSON.stringify({ distance, cost }),
  });
}
