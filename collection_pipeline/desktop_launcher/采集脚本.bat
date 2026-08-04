@echo off
rem =====================================================================
rem  !!! ???????? ASCII, ?????????? !!!
rem  DO NOT put any Chinese character in this file. Reason:
rem  cmd.exe reads a .bat with the codepage active when the process
rem  starts, and a "chcp" inside the file desyncs its own read offset
rem  by a byte -> GBK pairs re-pair -> lines split into garbage tokens
rem  ('ho', '...' not recognized as a command). Immune only if this
rem  file has zero bytes above 0x7F.
rem  All Chinese lives in the _*_zh.txt files, printed via TYPE, which
rem  never passes through the command parser.
rem =====================================================================
chcp 936 >nul
setlocal enabledelayedexpansion
title Relty Video Collection Pipeline
set "HERE=%~dp0"
set "PYDIR=E:\01Internship\Relty\diet_balance_baseline"
set "ROSTER="
set "NAS_SHARE=\\10.10.10.2\collector-data"
if exist "%HERE%_roster_path.txt" set /p ROSTER=<"%HERE%_roster_path.txt"

rem Reconnect Z: when the NAS address or network has changed.
if not exist "Z:\Processed Videos" (
  net use Z: /delete /y >nul 2>nul
  net use Z: "%NAS_SHARE%" /persistent:yes
  if errorlevel 1 (
    echo [ERROR] Cannot connect Z: to %NAS_SHARE%.
    echo         Enter the NAS account when Windows asks, then run again.
    pause
    exit /b 1
  )
)
if not exist "Z:\Processed Videos" (
  echo [ERROR] NAS archive folder not found: Z:\Processed Videos
  pause
  exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] python not found. Install Python 3.10+ with "Add to PATH".
  pause
  exit /b 1
)
if not exist "%PYDIR%\sd_video_pipeline.py" (
  echo [ERROR] pipeline scripts not found under: %PYDIR%
  pause
  exit /b 1
)
pushd "%PYDIR%"

:menu
cls
type "%HERE%_menu_zh.txt"
choice /c 12345670 /n /m "  1-7 / 0=exit : "
rem errorlevel must be tested high -> low.
rem 255 = choice could not read a key (piped/redirected stdin). Must exit,
rem otherwise the menu loops forever and [7] spawns endless windows.
if errorlevel 255 goto badinput
if errorlevel 8 goto end
if errorlevel 7 ( start "" explorer "Z:\Processed Videos" & goto menu )
if errorlevel 6 ( call :roster & goto menu )
if errorlevel 5 ( python "backfill_extract.py" --no-extract --keep-local & goto done )
if errorlevel 4 ( powershell -ExecutionPolicy Bypass -File "parallel_extract.ps1" & goto done )
if errorlevel 3 ( python "sd_video_pipeline.py" --register & goto done )
if errorlevel 2 ( python "sd_video_pipeline.py" --dry-run & goto done )
if errorlevel 1 ( python "sd_video_pipeline.py" --yes --no-extract & goto done )
goto menu

:roster
if defined ROSTER ( start "" notepad "!ROSTER!" ) else ( start "" explorer "Z:\Processed Videos\_pipeline" )
exit /b 0

:badinput
echo.
echo [ERROR] choice got no keyboard input.
echo         Run this script by DOUBLE-CLICK only.
echo         Never pipe or redirect anything into it.
echo.
pause >nul
goto end

:done
echo.
type "%HERE%_done_zh.txt"
pause >nul
goto menu

:end
popd
endlocal
