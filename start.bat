@echo off
title VideoGen Studio
echo ==========================================
echo    VideoGen Studio - AI Video Generator
echo ==========================================
echo.
echo Starting server on http://127.0.0.1:8765
echo.
cd /d "%~dp0"
python main.py
pause

