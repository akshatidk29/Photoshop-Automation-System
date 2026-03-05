@echo off
title Photoshop Intuk

echo.
echo ========================================
echo               Intuk
echo ========================================
echo.

cd /d "%~dp0"

:: Activate virtual environment
call photoshop\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found.
    echo Please run runOnce.bat first.
    pause
    exit /b 1
)

:: Verify Python 3.10
python --version 2>&1 | findstr "3.10" >nul
if errorlevel 1 (
    echo ERROR: This project requires Python 3.10
    echo Please recreate the virtual environment using runOnce.bat
    pause
    exit /b 1
)

:: Run automation
cd Code
python main.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo    An error occurred during execution
    echo ========================================
    pause
    exit /b 1
)

echo.
echo Session ended successfully.
pause
