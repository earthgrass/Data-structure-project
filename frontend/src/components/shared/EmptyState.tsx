// Phase 5.1 —— 通用空状态组件。
// 用于：调度结果未生成 / 比较未运行 / 场景缺失。

import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  description?: string;
  /** 顶部插图：可放 SVG / emoji / icon */
  illustration?: ReactNode;
  /** 编号提示步骤（如：选择目标 → 运行规划） */
  steps?: string[];
  /** 可选操作按钮 */
  actions?: ReactNode;
}

export function EmptyState({
  title,
  description,
  illustration,
  steps,
  actions,
}: EmptyStateProps) {
  return (
    <div className="result-empty">
      <div className="empty-illu" aria-hidden>
        {illustration ?? (
          <svg width="44" height="44" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 6h16M4 12h16M4 18h10"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
        )}
      </div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {steps && steps.length > 0 && (
        <div className="hint-steps">
          {steps.map((s, i) => (
            <div key={`step-${i}`}>
              <span style={{ color: 'var(--status-info)', fontWeight: 700 }}>
                {i + 1}.
              </span>{' '}
              {s}
            </div>
          ))}
        </div>
      )}
      {actions && <div className="btn-row" style={{ marginTop: 8 }}>{actions}</div>}
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
}

export function ErrorState({
  title = '请求失败',
  message,
  onRetry,
  onDismiss,
}: ErrorStateProps) {
  return (
    <div className="result-error" role="alert">
      <div className="error-illu" aria-hidden>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
          <path
            d="M12 7v6M12 16v.5"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <h3>{title}</h3>
      <p>{message}</p>
      {(onRetry || onDismiss) && (
        <div className="btn-row" style={{ marginTop: 4 }}>
          {onRetry && (
            <button className="btn btn-primary" onClick={onRetry}>
              重试
            </button>
          )}
          {onDismiss && (
            <button className="btn btn-secondary" onClick={onDismiss}>
              关闭
            </button>
          )}
        </div>
      )}
    </div>
  );
}
