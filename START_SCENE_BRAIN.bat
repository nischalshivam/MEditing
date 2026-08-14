@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime\production_editor\logs" mkdir "runtime\production_editor\logs"
echo [%date% %time%] Launcher started>>"runtime\production_editor\logs\launcher.log"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_SCENE_BRAIN.ps1"
if errorlevel 1 (
  echo Scene Brain failed to start. See:
  echo %~dp0runtime\production_editor\logs\launcher.log
  echo %~dp0runtime\production_editor\logs\server.log
  pause
  exit /b 1
)
endlocal
