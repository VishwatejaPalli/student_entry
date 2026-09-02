@echo off
setlocal enabledelayedexpansion
title Room Entry & Lab Management System
cd /d "%~dp0"

echo ===================================================
echo   Room Entry & Lab Management System (Windows)
echo ===================================================
echo.

:: 1. Detect Python Command (try "py -3", "python", "py")
set "PYTHON_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    goto :PYTHON_FOUND
)

python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :PYTHON_FOUND
)

py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto :PYTHON_FOUND
)

:PYTHON_NOT_FOUND
echo [ERROR] Python was not detected in your PATH!
echo.
echo Please do the following:
echo 1. Download Python 3.10+ from: https://www.python.org/downloads/
echo 2. Run the installer and MUST check:
echo    "[X] Add python.exe to PATH"
echo 3. If already installed, open Settings -> Apps -> App execution aliases,
echo    and turn OFF the aliases for "App Installer (python.exe)".
echo.
pause
exit /b 1

:PYTHON_FOUND
echo [INFO] Detected Python: !PYTHON_CMD!
!PYTHON_CMD! --version

:: 2. Check if existing venv is broken or from Linux (has bin/ instead of Scripts/)
if exist "venv\bin" (
    echo [INFO] Detected Linux virtual environment. Recreating for Windows...
    rmdir /s /q "venv"
)

:: 3. Setup Windows virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Creating Windows virtual environment (venv)...
    if exist "venv" rmdir /s /q "venv"
    !PYTHON_CMD! -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    
    echo [2/3] Installing dependencies from requirements.txt...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    call venv\Scripts\activate.bat
)

:: 4. Copy .env configuration if missing
if not exist ".env" (
    if exist ".env.example" (
        echo [3/3] Creating default .env configuration...
        copy .env.example .env >nul
    )
)

echo.
echo ===================================================
echo   System is ready!
echo   Local Web App: http://localhost:8000
echo   Admin Panel:   http://localhost:8000/admin/students
echo ===================================================
echo   Press Ctrl+C in this terminal to stop the server.
echo ===================================================
echo.

:: 5. Launch server
python -m uvicorn main:app --host 0.0.0.0 --port 8000

if errorlevel 1 (
    echo.
    echo [ERROR] Server encountered an error and stopped.
)
pause
