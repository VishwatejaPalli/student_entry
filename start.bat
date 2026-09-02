@echo off
title Room Entry ^& Lab Management System
cd /d "%~dp0"

echo ===================================================
echo   Room Entry ^& Lab Management System (Windows)
echo ===================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please download and install Python 3.10+ from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Setup virtual environment if not present
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Creating Python virtual environment (venv)...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    
    echo [2/3] Installing required packages...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    call venv\Scripts\activate.bat
)

:: Create .env if missing
if not exist ".env" (
    if exist ".env.example" (
        echo [3/3] Setting up default configuration (.env)...
        copy .env.example .env >nul
    )
)

echo.
echo ===================================================
echo   Server is running!
echo   Local Web App: http://localhost:8000
echo   Admin Panel:   http://localhost:8000/admin/students
echo ===================================================
echo   Press Ctrl+C in this window to stop the server.
echo ===================================================
echo.

uvicorn main:app --host 0.0.0.0 --port 8000
pause
