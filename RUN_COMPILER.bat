@echo off
title GhostEye Compiler Agent
echo =======================================================
echo      STARTING GHOSTEYE COMPILER AGENT CLIENT
echo =======================================================
cd /d "%~dp0"
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your PATH.
    pause
    exit /b
)
echo Launching GUI Compiler Editor Agent...
python compiler_agent.py
if %errorlevel% neq 0 (
    echo An error occurred while launching compiler_agent.py
    pause
)
