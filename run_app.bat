@echo off
setlocal

:: Activate UV Environment
echo Activating UV Environment...
call .venv\Scripts\activate.bat

:: Start Backend
start "Spleeter-Demucs Backend" cmd /k "call .venv\Scripts\activate.bat && python backend/main.py"

:: Start Frontend
start "Spleeter-Demucs Frontend" cmd /k "cd frontend && npm run dev"

echo Application started!
echo Frontend: http://localhost:5173
echo Backend: http://localhost:8000
pause
