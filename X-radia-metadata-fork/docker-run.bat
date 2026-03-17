@echo off
REM X-radia Metadata Extractor - Docker Quick Run (Windows)
REM =======================================================
REM
REM IMPORTANT: XradiaPy requires your HOST system's Python!
REM This script automatically detects your Python 2.7 installation.
REM
REM Usage:
REM   docker-run.bat                                    # Auto-detect
REM   docker-run.bat C:\path\to\txrm\files             # Specify data
REM   docker-run.bat C:\path\to\data C:\Python27       # Specify both

setlocal enabledelayedexpansion

echo.
echo ================================================================
echo          X-RADIA METADATA EXTRACTOR - Docker
echo ================================================================
echo.

REM Check Docker
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not installed
    echo Install from: https://www.docker.com/get-started
    pause
    exit /b 1
)

docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not running
    echo Please start Docker Desktop
    pause
    exit /b 1
)
echo [OK] Docker is available

REM Get script directory
set SCRIPT_DIR=%~dp0

REM Parse arguments
set DATA_PATH=%~1
set PYTHON_PATH=%~2

if "%DATA_PATH%"=="" set DATA_PATH=%SCRIPT_DIR%sample_data

REM Auto-detect Python 2.7 if not specified
if "%PYTHON_PATH%"=="" (
    echo.
    echo Detecting host Python 2.7...
    
    REM Check common Windows Python locations
    if exist "C:\Python27\python.exe" (
        set PYTHON_PATH=C:\Python27
        echo [OK] Found Python at C:\Python27
    ) else if exist "C:\Program Files\Python27\python.exe" (
        set PYTHON_PATH=C:\Program Files\Python27
        echo [OK] Found Python at C:\Program Files\Python27
    ) else if exist "C:\Program Files (x86)\Python27\python.exe" (
        set PYTHON_PATH=C:\Program Files (x86)\Python27
        echo [OK] Found Python at C:\Program Files (x86)\Python27
    ) else (
        echo [!] Python 2.7 not found in standard locations
        echo     Specify path: docker-run.bat C:\data C:\Python27
    )
    
    REM Check if detected Python has XradiaPy
    if defined PYTHON_PATH (
        "!PYTHON_PATH!\python.exe" -c "import XradiaPy" >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            echo [OK] XradiaPy is available
        ) else (
            echo [!] XradiaPy not found in detected Python
        )
    )
)

REM Create directories
if not exist "%SCRIPT_DIR%sample_data" mkdir "%SCRIPT_DIR%sample_data"
if not exist "%SCRIPT_DIR%output" mkdir "%SCRIPT_DIR%output"

REM Build image
echo.
echo Building Docker image...
docker build -t xradia-metadata:latest "%SCRIPT_DIR%"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)
echo [OK] Image ready

REM Prepare docker command
set DOCKER_CMD=docker run -it --rm
set DOCKER_CMD=%DOCKER_CMD% -v "%DATA_PATH%":/data
set DOCKER_CMD=%DOCKER_CMD% -v "%SCRIPT_DIR%output":/output
set DOCKER_CMD=%DOCKER_CMD% -v "%SCRIPT_DIR%contacts.csv":/app/contacts.csv:ro

if defined PYTHON_PATH (
    if exist "%PYTHON_PATH%" (
        set DOCKER_CMD=%DOCKER_CMD% -v "%PYTHON_PATH%":/host_python:ro
    )
)

set DOCKER_CMD=%DOCKER_CMD% xradia-metadata:latest

REM Show config
echo.
echo Configuration:
echo   Data:   %DATA_PATH%
echo   Output: %SCRIPT_DIR%output
if defined PYTHON_PATH echo   Python: %PYTHON_PATH%

REM Run
echo.
echo Starting container...
echo.
%DOCKER_CMD%

pause
