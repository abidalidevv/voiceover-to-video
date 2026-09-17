@echo off
title VideoGen Studio (Standalone EXE Mode)
color 0a

echo ================================================================
echo    VideoGen Studio - AI YouTube Full HD Video Generator
echo               [STANDALONE EXECUTABLE RUNNER]
echo ================================================================
echo.

cd /d "%~dp0"

:: Check if dist\VideoGenStudio\VideoGenStudio.exe exists
if exist "%~dp0dist\VideoGenStudio\VideoGenStudio.exe" (
    echo [OK] Starting Standalone VideoGenStudio.exe ...
    echo App will open automatically at http://127.0.0.1:8765
    echo.
    start "" "%~dp0dist\VideoGenStudio\VideoGenStudio.exe"
    exit /b 0
)

if exist "%~dp0VideoGenStudio.exe" (
    echo [OK] Starting Standalone VideoGenStudio.exe ...
    echo App will open automatically at http://127.0.0.1:8765
    echo.
    start "" "%~dp0VideoGenStudio.exe"
    exit /b 0
)

echo [ERROR] VideoGenStudio.exe was not found!
echo Expected location: dist\VideoGenStudio\VideoGenStudio.exe
echo Run 'build_exe.bat' to build the standalone executable.
echo.
pause
exit /b 1
