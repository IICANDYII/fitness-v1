@echo off
title Fitness Dashboard Launcher

set PYTHON=E:\Anaconda\envs\diet\python.exe
set API_DIR=D:\WorkPath\fitness
set FRONT_DIR=D:\WorkPath\fitness\agent_service\reports

echo [1/4] Kill port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /PID %%p /F >nul 2>&1
)

echo [2/4] Kill port 8080...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8080 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /PID %%p /F >nul 2>&1
)

ping -n 2 127.0.0.1 >nul

echo [3/4] Starting API server (port 8000)...
start "API Server :8000" /D "%API_DIR%" cmd /k "%PYTHON% -m uvicorn agent_service.reports.api:app --host 0.0.0.0 --port 8000 --log-level info"

echo [4/4] Starting frontend server (port 8080)...
start "Frontend :8080" /D "%FRONT_DIR%" cmd /k "%PYTHON% -m http.server 8080 --bind 0.0.0.0"

ping -n 4 127.0.0.1 >nul

start "" "http://localhost:8080/training_dashboard.html"

echo.
echo [OK] Services started
echo   Frontend : http://localhost:8080/training_dashboard.html
echo   API      : http://localhost:8000/api
echo.
echo Close "API Server" and "Frontend" windows to stop services.
