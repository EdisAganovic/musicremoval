@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo     Audio Splitter Pro Startup Utility
echo ==========================================
echo.

:: 1. Clear the port using PowerShell (much more robust)
echo [1/3] Checking Port 5170...
powershell -Command "$p = Get-NetTCPConnection -LocalPort 5170 -ErrorAction SilentlyContinue; if ($p) { echo '[System] Found active process on 5170. Killing...'; $p | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"

:: 2. Launch Backend
echo [2/3] Launching Backend...
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
REM Using 'uv run --no-sync' ensures fast startup without file locking issues.
start "AudioSplitter-Backend" cmd /k "set PYTHONIOENCODING=utf-8&& set PYTHONUTF8=1&& uv run --no-sync uvicorn backend.backend:app --host 0.0.0.0 --port 5170 --reload --reload-dir backend --log-level warning"

:: 3. Launch Frontend
echo [3/3] Launching Frontend...
if exist "frontend" (
    start "AudioSplitter-Frontend" cmd /k "cd frontend && npm run dev"
)

echo.
echo ==========================================
echo    Startup complete! Check new windows.
echo ==========================================
echo.
pause
