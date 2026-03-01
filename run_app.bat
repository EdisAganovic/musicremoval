@echo off
setlocal

:: Activate UV Environment
echo Activating UV Environment...
call .venv\Scripts\activate.bat

:: Start Backend with Hot Reload (exclude temp directories)
start "Spleeter-Demucs Backend" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-exclude '_temp/*' --reload-exclude 'spleeter_out/*' --reload-exclude 'demucs_out/*' --reload-exclude 'downloads/*' --reload-exclude 'nomusic/*' --reload-exclude 'uploads/*' --log-level warning"

:: Start Frontend
start "Spleeter-Demucs Frontend" cmd /k "cd frontend && npm run dev"

echo Application started!
echo Frontend: http://localhost:5173
echo Backend: http://localhost:8000 (with hot reload)
echo.
echo Backend will show only warnings and errors (no INFO spam)
pause
