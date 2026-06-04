@echo off

set PROJDIR=E:\fitness_code
set PYTHONPATH=E:\fitness_code
set PYTHON=C:\Users\qinzi\.conda\envs\fitness\python.exe

echo =============================================
echo  Fitness Dashboard Launcher
echo =============================================
echo.

:: Step 0: Kill ports 8000 and 8002
echo [0/3] Clearing ports...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8002 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: Step 1: PostgreSQL via Docker
echo [1/3] Checking Docker container...
docker inspect -f "{{.State.Running}}" postgres-pgvector 2>nul | find "true" >nul
if %errorlevel% neq 0 (
    echo   Starting postgres-pgvector...
    docker start postgres-pgvector >nul 2>&1
    timeout /t 3 /nobreak >nul
) else (
    echo   PostgreSQL OK.
)

:: Step 2: Start APIs
echo [2/3] Starting Dashboard API :8000 ...
start "Dashboard API :8000" cmd /k "cd /d E:\fitness_code && set PYTHONPATH=E:\fitness_code && C:\Users\qinzi\.conda\envs\fitness\python.exe -m uvicorn agent_service.reports.api:app --host 0.0.0.0 --port 8000 --reload"

echo [3/3] Starting Gym Analyzer API :8002 ...
start "Gym Analyzer :8002" cmd /k "cd /d E:\fitness_code && set PYTHONPATH=E:\fitness_code && C:\Users\qinzi\.conda\envs\fitness\python.exe -m uvicorn gym_analyzer.api:app --host 0.0.0.0 --port 8002 --reload"

echo.
echo =============================================
echo   Dashboard : http://localhost:8000
echo   Analyzer  : http://localhost:8002/analyzer
echo   API docs  : http://localhost:8000/docs
echo =============================================
echo.
pause