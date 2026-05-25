@echo off
title GhostEye SIEM Ingestion Server
echo =======================================================
echo      STARTING GHOSTEYE SIEM INGESTION SERVER
echo =======================================================
cd /d "%~dp0"
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your PATH environment variable.
    echo Please install Python 3 and check the box "Add Python to PATH".
    pause
    exit /b
)
echo Checking dependencies...
python -c "import fastapi, uvicorn, requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing missing python dependencies...
    pip install fastapi uvicorn requests python-docx
)
echo Server is launching at http://127.0.0.1:8000
echo Press Ctrl+C to terminate the server.
echo -------------------------------------------------------
python server.py
pause
