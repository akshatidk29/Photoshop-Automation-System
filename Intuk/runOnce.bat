@echo off
title Python Environment Setup

cd /d "%~dp0"

echo Checking Python 3.10...
py -3.10 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.10 not found.
    pause
    exit /b 1
)

echo Creating virtual environment...
py -3.10 -m venv photoshop

echo Activating virtual environment...
call photoshop\Scripts\activate.bat

echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r Code\requirements.txt

echo.
echo Setup completed successfully!
pause
