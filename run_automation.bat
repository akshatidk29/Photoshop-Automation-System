@echo off
title Photoshop Automation
echo.
echo ========================================
echo    PHOTOSHOP AUTOMATION TOOL
echo ========================================
echo.
echo Starting automation interface...
echo.

:: Change to script directory
cd /d "%~dp0"

:: Activate conda environment and run
call conda activate photoshop
if errorlevel 1 (
    echo WARNING: Could not activate 'photoshop' conda environment
    echo Attempting to run with default Python...
)

:: Run the main script
python main.py

:: Check exit code
if errorlevel 1 (
    echo.
    echo ========================================
    echo    An error occurred during execution
    echo ========================================
    pause
)

echo.
echo Automation session ended.
pause
