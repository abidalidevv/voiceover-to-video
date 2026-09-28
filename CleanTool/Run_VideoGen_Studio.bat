@echo off
title VideoGen Studio - AI YouTube Full HD Video Studio
color 0b

echo ================================================================
echo    VideoGen Studio - Automated YouTube Full HD Video Studio
echo ================================================================
echo.

cd /d "%~dp0"

:: 1. Register portable FFmpeg engine from bin folder
if exist "%~dp0bin\ffmpeg.exe" (
    set "PATH=%~dp0bin;%PATH%"
    echo [OK] Portable FFmpeg engine registered.
)

:: 2. Detect working Python interpreter
set "PY_EXE="

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_EXE=python"
    goto :FOUND_PYTHON
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_EXE=py"
    goto :FOUND_PYTHON
)

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0.venv\Scripts\python.exe"
    goto :FOUND_PYTHON
)

echo [ERROR] Python was not detected on your system.
echo Please install Python 3.10+ from https://www.python.org/
echo (Check "Add Python to PATH" during installation)
echo.
pause
exit /b 1

:FOUND_PYTHON
echo [OK] Python found:
%PY_EXE% --version
echo.

echo Starting VideoGen Studio Engine...
echo Interface will open automatically at http://127.0.0.1:8765
echo.

%PY_EXE% desktop_launcher.py

if %errorlevel% neq 0 (
    echo.
    echo [Notice] VideoGen Studio has closed.
    pause
)
