@echo off
echo ========================================
echo   Killing processes on ports 8000, 5173, 5174
echo ========================================
echo.

REM Kill process on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    echo [Port 8000] Killing PID %%a...
    taskkill /F /PID %%a 2>nul
)

REM Kill process on port 5173
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5173" ^| find "LISTENING"') do (
    echo [Port 5173] Killing PID %%a...
    taskkill /F /PID %%a 2>nul
)

REM Kill process on port 5174
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5174" ^| find "LISTENING"') do (
    echo [Port 5174] Killing PID %%a...
    taskkill /F /PID %%a 2>nul
)

echo.
echo ========================================
echo   Done! All ports cleared.
echo ========================================
pause
