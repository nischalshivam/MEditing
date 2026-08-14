@echo off
setlocal
title ResearchCut Editor - System Check
cd /d "%~dp0"
echo ResearchCut Editor 2.1 system check
echo.
where node >nul 2>nul && (node --version) || echo [MISSING] Node.js LTS
where ffmpeg >nul 2>nul && (ffmpeg -version 2>nul | findstr /b "ffmpeg version") || echo [MISSING] FFmpeg
where ffprobe >nul 2>nul && (ffprobe -version 2>nul | findstr /b "ffprobe version") || echo [MISSING] FFprobe
where python >nul 2>nul && (python --version) || echo [OPTIONAL MISSING] Python - editor works, VText does not
if exist "tools\vtext\check.py" (
  where python >nul 2>nul && python "tools\vtext\check.py"
) else (
  echo [MISSING] Bundled VText folder
)
echo.
echo If all mandatory items are present, run START_EDITOR.bat.
pause
