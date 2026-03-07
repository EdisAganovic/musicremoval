@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo       DemucsPleeter Startup Utility
echo ==========================================
echo.

:: 1. Clear the port using PowerShell (much more robust)
echo [1/3] Checking Port 5170...
powershell -Command "$p = Get-NetTCPConnection -LocalPort 5170 -ErrorAction SilentlyContinue; if ($p) { echo '[System] Found active process on 5170. Killing...'; $p | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"

:: 2. Launch Backend
echo [2/3] Launching Backend...
if exist ".venv\Scripts\activate.bat" (
    REM We use start "" to launch in a new window
    start "Demucs-Backend" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn backend.backend:app --host 0.0.0.0 --port 5170 --reload --reload-exclude data --reload-exclude download --reload-exclude downloads --reload-exclude nomusic --reload-exclude uploads --reload-exclude _temp --reload-exclude _processing_intermediates --reload-exclude log.txt --log-level warning"
) else (
    echo [Error] Could not find .venv folder.
)

:: 3. Launch Frontend
echo [3/3] Launching Frontend...
if exist "frontend" (
    start "Demucs-Frontend" cmd /k "cd frontend && npm run dev"
)

echo.
echo ==========================================
echo    Startup complete! Check new windows.
echo ==========================================
echo.
pause
