// main —— React 入口。

import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { ErrorBoundary } from './components/shared/ErrorBoundary';

// Phase 5 —— design tokens + 全局 reset + 组件布局
// 拆分到多个 CSS 文件以避免单一巨型样式文件。
//
// ErrorBoundary 包裹 App：捕获 React 渲染异常，避免整个页面闪退；
// 任何未捕获错误会显示带「刷新页面 / 尝试恢复」按钮的友好提示，
// 并把 componentStack 写入 console.error。

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);