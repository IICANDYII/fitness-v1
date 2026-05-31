@echo off
chcp 65001 >nul
cd /d D:\WorkPath\fitness

echo ============================================
echo  Fitness Dashboard Launcher
echo ============================================
echo.

:: Step 0: Kill any existing process on port 8000
echo [0/4] Checking for existing process on port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%p on port 8000...
    taskkill /PID %%p /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: Step 1: Start PostgreSQL service
sc query postgresql-x64-18 | find "RUNNING" >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/4] Starting PostgreSQL service...
    net start postgresql-x64-18
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to start PostgreSQL. Try running as Administrator.
        pause
        exit /b 1
    )
    timeout /t 3 /nobreak >nul
) else (
    echo [1/4] PostgreSQL already running. OK.
)

:: Step 2: Start FastAPI backend (reports + planner on port 8000)
echo [2/4] Starting backend API on http://localhost:8000 ...
start "Fitness API :8000" cmd /k "python -m uvicorn agent_service.reports.api:app --host 0.0.0.0 --port 8000 --reload"

:: Step 3: Wait for uvicorn to be ready
echo [3/4] Waiting for API server to start...
timeout /t 4 /nobreak >nul

:: Step 4: Open frontend pages
echo [4/4] Opening frontends...
echo   Planner   -^> http://localhost:8000/plan-viewer
start "" "http://localhost:8000/plan-viewer"

echo   Reports   -^> training_dashboard.html
start "" "D:\WorkPath\fitness\agent_service\reports\training_dashboard.html"

echo   HR Detail -^> hr_detail.html
start "" "D:\WorkPath\fitness\agent_service\reports\hr_detail.html"

echo.
echo ============================================
echo   Backend  : http://localhost:8000
echo   Planner  : http://localhost:8000/plan-viewer
echo   API docs : http://localhost:8000/docs
echo ============================================
echo.
pause
