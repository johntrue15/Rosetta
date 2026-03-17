@echo off
REM X-radia Metadata Extractor - Windows Quick Start
REM ================================================
REM Double-click this file to start!

REM Enable ANSI colors on Windows 10+
set VIRTUAL_TERMINAL_PROCESSING=1

REM Find Python
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python start.py
    pause
    exit /b 0
)

REM Try common Python paths
if exist "C:\Python27\python.exe" (
    C:\Python27\python.exe start.py
    pause
    exit /b 0
)

if exist "C:\Python39\python.exe" (
    C:\Python39\python.exe start.py
    pause
    exit /b 0
)

echo.
echo [ERROR] Python not found!
echo.
echo Please install Python from: https://www.python.org/downloads/
echo.
pause
