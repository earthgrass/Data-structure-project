#!/usr/bin/env bash
# ====================================================================
#  LogiRoute Phase 5 Dashboard —— 一键启动开发环境（Unix / Git Bash）
#  同时启动后端 (uvicorn :8000) 与前端 (Vite :5172)
#  Ctrl+C 终止脚本；会自动杀掉两个子进程
# ====================================================================

set -euo pipefail

# 切到项目根目录（脚本所在目录的上一级）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "[LogiRoute] Working directory: $(pwd)"

# —— 检查 Python ——
if ! command -v python >/dev/null 2>&1; then
  echo "[ERROR] Python not found in PATH. Please install Python 3.11+."
  exit 1
fi

# —— 安装 frontend 依赖（缺失时） ——
if [ ! -d "frontend/node_modules" ]; then
  echo "[WARN] frontend/node_modules missing. Running npm install..."
  (cd frontend && npm install)
fi

# —— 后端 ——
echo "[LogiRoute] Starting backend on http://127.0.0.1:8000 ..."
PYTHONPATH=src python -m uvicorn logiroute.api:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# —— 前端 ——
echo "[LogiRoute] Starting Vite dev on http://localhost:5172 ..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

cleanup() {
  echo
  echo "[LogiRoute] Stopping services ..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  echo "[LogiRoute] Stopped."
}
trap cleanup INT TERM EXIT

echo
echo "[LogiRoute] Both services starting."
echo "[LogiRoute] Open http://localhost:5172/ in your browser."
echo "[LogiRoute] Press Ctrl+C to stop both services."
echo

# 等待任一进程结束
wait -n "$BACKEND_PID" "$FRONTEND_PID" || true
cleanup
