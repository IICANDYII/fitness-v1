@echo off
setlocal
set "SCRIPT=%~dp0GPlus-BatchTimeSync.ps1"

if not exist "%SCRIPT%" (
  echo Cannot find: %SCRIPT%
  pause
  exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%

