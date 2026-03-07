@echo off
SETLOCAL EnableDelayedExpansion

echo ==========================================
echo       GPU Acceleration Fix for Demucs
echo ==========================================
echo.
echo This script will uninstall the CPU version of PyTorch
echo and install the GPU version (CUDA 12.8).
echo.
echo WARNING: This requires an NVIDIA GPU and CUDA drivers.
echo.

:: Check for .venv
if not exist ".venv" (
    echo [ERROR] .venv folder not found!
    echo Please ensure you are running this from the project root.
    pause
    exit /b
)

echo [1/3] Activating environment...
call .venv\Scripts\activate.bat

echo [2/3] Uninstalling CPU-only packages...
uv pip uninstall torch torchvision torchaudio

echo [3/3] Installing GPU-accelerated PyTorch (cu128)...
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

echo.
echo ==========================================
echo        GPU FIX COMPLETED SUCCESSFULLY
echo ==========================================
echo.
echo You can now close this window and restart the application.
echo If separation is still slow, check your NVIDIA driver version.
echo.
pause
