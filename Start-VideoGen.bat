@echo off
setlocal enabledelayedexpansion
title VideoGen Studio - AI YouTube Full HD Video Generator
color 0b

echo ================================================================
echo    VideoGen Studio - Automated YouTube Full HD Video Studio
echo ================================================================
echo.

cd /d "%~dp0"

:: 1. Check Python installation
set "PY_CMD=python"
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    py --version >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set "PY_CMD=py"
    ) else (
        echo [ERROR] Python is not installed or not in your Windows PATH!
        echo.
        echo Solution 1: Download and run the standalone VideoGenStudio.exe
        echo             (Does not require Python at all!^)
        echo.
        echo Solution 2: Install Python 3.10+ from https://www.python.org/downloads/
        echo             Make sure to check "Add Python to PATH" during installation.
        echo.
        pause
        exit /b 1
    )
)

echo [OK] Python detected:
%PY_CMD% --version

:: 2. Check or initialize Virtual Environment (.venv)
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [SETUP] Initializing clean virtual environment (.venv)...
    %PY_CMD% -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [WARNING] Could not create virtual environment. Using system Python.
        set "APP_PYTHON=%PY_CMD%"
    ) else (
        set "APP_PYTHON=.venv\Scripts\python.exe"
        echo [SETUP] Installing required dependencies (FastAPI, Uvicorn, Groq, etc.)...
        !APP_PYTHON! -m pip install --upgrade pip >nul 2>&1
        !APP_PYTHON! -m pip install -r requirements.txt
    )
) else (
    set "APP_PYTHON=.venv\Scripts\python.exe"
)

:: 3. Check FFmpeg availability
set "HAS_FFMPEG=0"
if exist "bin\ffmpeg.exe" set "HAS_FFMPEG=1"
if %HAS_FFMPEG% EQU 0 (
    where ffmpeg >nul 2>&1
    if !ERRORLEVEL! EQU 0 set "HAS_FFMPEG=1"
)

if %HAS_FFMPEG% EQU 0 (
    echo.
    echo [NOTICE] FFmpeg video engine not found locally.
    echo          Attempting automated download of portable FFmpeg...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Write-Host 'Downloading portable FFmpeg...'; if (!(Test-Path 'bin')) { New-Item -ItemType Directory -Path 'bin' | Out-Null }; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile 'bin\ffmpeg.zip'; Expand-Archive -Path 'bin\ffmpeg.zip' -DestinationPath 'bin\temp' -Force; Get-ChildItem -Path 'bin\temp' -Filter 'ffmpeg.exe' -Recurse | Copy-Item -Destination 'bin\ffmpeg.exe' -Force; Get-ChildItem -Path 'bin\temp' -Filter 'ffprobe.exe' -Recurse | Copy-Item -Destination 'bin\ffprobe.exe' -Force; Remove-Item 'bin\temp' -Recurse -Force; Remove-Item 'bin\ffmpeg.zip' -Force; Write-Host 'Portable FFmpeg installed successfully!' } catch { Write-Host 'Manual download recommended: install FFmpeg or use pre-bundled release.' }"
)

:: 4. Launch VideoGen Studio Engine
echo.
echo ================================================================
echo Starting VideoGen Studio Engine & Native Desktop Interface...
echo Local Server: http://127.0.0.1:8765
echo ================================================================
echo.

%APP_PYTHON% desktop_launcher.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with code %ERRORLEVEL%.
    pause
)
