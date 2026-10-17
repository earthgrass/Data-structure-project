@echo off
REM ====================================================================
REM  LogiRoute Phase 5 Dashboard —— 一键启动开发环境
REM  同时启动后端 (uvicorn :8000) 与前端 (Vite :5172)
REM  Ctrl+C 关闭任一窗口即终止对应进程
REM ====================================================================

setlocal enabledelayedexpansion

REM 切到项目根目录（脚本所在目录的上一级）
cd /d "%~dp0\.."

echo [LogiRoute] Working directory: %cd%
echo.

REM —— 检查 Python 环境 ——
where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found in PATH. Please install Python 3.11+.
  pause
  exit /b 1
)

REM —— 检查 node_modules ——
if not exist "frontend\node_modules" (
  echo [WARN] frontend\node_modules missing. Running npm install...
  cd frontend
  call npm install
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
  )
  cd ..
)

REM —— 后端窗口 ——
echo [LogiRoute] Starting backend on http://127.0.0.1:8000 ...
start "LogiRoute-Backend" cmd /k "set PYTHONPATH=src && python -m uvicorn logiroute.api:app --host 127.0.0.1 --port 8000"

REM —— 前端窗口 ——
echo [LogiRoute] Starting Vite dev on http://localhost:5172 ...
start "LogiRoute-Frontend" cmd /k "cd /d %cd%\frontend && npm run dev"

echo.
echo [LogiRoute] Both services starting in separate windows.
echo [LogiRoute] Open http://localhost:5172/ in your browser.
echo [LogiRoute] Close the spawned windows (or Ctrl+C in them) to stop.
echo.
endlocal
