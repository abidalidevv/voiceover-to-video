@echo off
title Building VideoGen Studio Standalone Executable
color 0a

echo ================================================================
echo       VideoGen Studio - Standalone Windows Executable Builder
echo ================================================================
echo.

cd /d "%~dp0"

echo [1/4] Cleaning previous builds...
if exist "build" rd /s /q "build"
if exist "dist\VideoGenStudio" rd /s /q "dist\VideoGenStudio"

echo.
echo [2/4] Compiling VideoGenStudio.exe via PyInstaller...
pyinstaller --clean videogen_studio.spec -y

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PyInstaller compilation failed! Check errors above.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [3/5] Bundling portable FFmpeg, assets, and frontend...
if not exist "dist\VideoGenStudio\bin" mkdir "dist\VideoGenStudio\bin"
if exist "bin\ffmpeg.exe" (
    copy /y "bin\ffmpeg.exe" "dist\VideoGenStudio\bin\ffmpeg.exe" >nul
    copy /y "bin\ffprobe.exe" "dist\VideoGenStudio\bin\ffprobe.exe" >nul
    echo       Portable FFmpeg binaries copied to dist\VideoGenStudio\bin\
)

if not exist "dist\VideoGenStudio\data" mkdir "dist\VideoGenStudio\data"
if not exist "dist\VideoGenStudio\data\thumbnails" mkdir "dist\VideoGenStudio\data\thumbnails"
if not exist "dist\VideoGenStudio\data\seo" mkdir "dist\VideoGenStudio\data\seo"
if exist "data\settings.json" copy /y "data\settings.json" "dist\VideoGenStudio\data\settings.json" >nul
if exist "data\sfx" xcopy /e /i /y "data\sfx" "dist\VideoGenStudio\data\sfx" >nul
if exist "data\assets" xcopy /e /i /y "data\assets" "dist\VideoGenStudio\data\assets" >nul
if exist "frontend" xcopy /e /i /y "frontend" "dist\VideoGenStudio\frontend" >nul
echo       Frontend and assets copied to dist\VideoGenStudio\

echo.
echo [4/5] Creating launcher shortcuts and readme in release folder...
(
echo @echo off
echo title VideoGen Studio
echo cd /d "%%~dp0"
echo start "" "VideoGenStudio.exe"
) > "dist\VideoGenStudio\Launch-VideoGenStudio.bat"

(
echo ================================================================
echo VideoGen Studio - AI YouTube Full HD Video Generator (Portable)
echo ================================================================
echo.
echo HOW TO RUN:
echo 1. Double-click "VideoGenStudio.exe" (or "Launch-VideoGenStudio.bat"^).
echo 2. The local AI engine starts and opens automatically in desktop window.
echo 3. Zero setup required - Python, FFmpeg, and all dependencies are bundled.
echo.
echo All generated videos will be saved in the "data\output\" folder.
) > "dist\VideoGenStudio\README_HOW_TO_RUN.txt"

echo.
echo [5/5] Creating portable ZIP archive: dist\VideoGenStudio-Windows-Portable.zip ...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\VideoGenStudio\*' -DestinationPath 'dist\VideoGenStudio-Windows-Portable.zip' -Force"

echo.
echo ================================================================
echo [SUCCESS] Standalone Executable Built Successfully!
echo Output Folder: %~dp0dist\VideoGenStudio\
echo Executable:    %~dp0dist\VideoGenStudio\VideoGenStudio.exe
echo Portable Zip:  %~dp0dist\VideoGenStudio-Windows-Portable.zip
echo ================================================================
echo.
pause

