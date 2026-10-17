// Phase 5.2 —— ErrorBoundary：捕获 React 渲染错误并显示可读信息。
// 任何 React 渲染异常都会被捕获，避免整个页面「白屏 / 闪退」。

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  componentStack: string | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null, componentStack: null };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // 持久化到 console.error 方便用户从 DevTools 看到
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] React 渲染异常：', error, info.componentStack);
    this.setState({ componentStack: info.componentStack ?? null });
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null, componentStack: null });
  };

  render() {
    if (!this.state.hasError || !this.state.error) {
      return this.props.children;
    }
    return (
      <div className="dashboard-shell">
        <div className="global-error-banner severity-critical" role="alert">
          <div className="geb-text">
            <div className="geb-title">⚠ 页面渲染异常</div>
            <div className="geb-message">
              {this.state.error.message || String(this.state.error)}
            </div>
            <div className="geb-recovery">
              请尝试刷新页面（Ctrl+Shift+R 强制刷新）。如反复出现，请把上方的错误信息与浏览器控制台日志提供给开发者。
            </div>
          </div>
          <div className="geb-actions">
            <button
              className="btn btn-secondary"
              onClick={() => window.location.reload()}
            >
              刷新页面
            </button>
            <button className="btn btn-ghost" onClick={this.handleReset}>
              尝试恢复
            </button>
          </div>
        </div>
      </div>
    );
  }
}
