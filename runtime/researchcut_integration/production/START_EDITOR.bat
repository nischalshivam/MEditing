@echo off
setlocal
title ResearchCut Editor
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Install Node.js 18 or newer, then run this file again.
  pause
  exit /b 1
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo FFmpeg was not found in PATH. Install FFmpeg, then run this file again.
  pause
  exit /b 1
)
where ffprobe >nul 2>nul
if errorlevel 1 (
  echo FFprobe was not found in PATH. Install the complete FFmpeg package, then run this file again.
  pause
  exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
  echo NOTE: Python was not found. The editor and text-free renders will work,
  echo but narration-synced VText will stay unavailable until Python is installed.
  echo.
)
node server.js
if errorlevel 1 pause
