// main —— React 入口。

import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';

// Phase 5 —— design tokens + 全局 reset + 组件布局
// 拆分到多个 CSS 文件以避免单一巨型样式文件。

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);