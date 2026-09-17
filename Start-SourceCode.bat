@echo off
title VideoGen Studio (Source Code Mode - Python)
color 0b

echo ================================================================
echo    VideoGen Studio - AI YouTube Full HD Video Generator
echo                 [SOURCE CODE RUNNER - PYTHON]
echo ================================================================
echo.

cd /d "%~dp0"

:: 1. Register portable FFmpeg if present in bin folder
if exist "%~dp0bin\ffmpeg.exe" (
    set "PATH=%~dp0bin;%PATH%"
    echo [OK] Portable FFmpeg engine registered from bin\
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

echo [ERROR] Python 3.10+ was not found on your system!
echo To run the source code, please install Python or run Start-VideoGen-Exe.bat instead.
echo.
pause
exit /b 1

:FOUND_PYTHON
echo [OK] Using Python:
%PY_EXE% --version
echo.

echo Starting VideoGen Studio (Source Code Mode)...
echo App will open automatically at http://127.0.0.1:8765
echo.

%PY_EXE% desktop_launcher.py

if %errorlevel% neq 0 (
    echo.
    echo ================================================================
    echo [ERROR] Application exited with error code: %errorlevel%
    echo ================================================================
    pause
)
