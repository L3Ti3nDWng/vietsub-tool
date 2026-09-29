@echo off
setlocal
cd /d "%~dp0"

set "PATH=%~dp0bin;%PATH%"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment 'venv' not found.
    pause
    exit /b 1
)

echo ========================================================
echo   Starting Douyin Translator Pro...
echo ========================================================
echo.

venv\Scripts\python.exe main.py

if errorlevel 1 (
    echo.
    echo [WARNING] Application stopped with error code %ERRORLEVEL%.
    pause
)
endlocal
