@echo off
title Complete Fix Tool - PyTorch DLL Error
cd /d "%~dp0"

echo ============================================
echo      COMPLETE FIX TOOL - PyTorch DLL
echo ============================================
echo.
echo This script will attempt to fix the torch
echo DLL loading error automatically.
echo.
echo Steps:
echo  1. Update Visual C++ Redistributable
echo  2. Test if torch works
echo  3. If not, reinstall PyTorch
echo  4. Final verification
echo.
echo ============================================
echo.

:: Check for admin rights
net session >nul 2>&1
if errorlevel 1 (
    echo ============================================
    echo  ERROR: ADMINISTRATOR REQUIRED
    echo ============================================
    echo.
    echo Please right-click this file and select
    echo "Run as administrator"
    echo.
    pause
    exit /b 1
)

:: Activate virtual environment first
if not exist "photoshop\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run runOnce.bat first.
    pause
    exit /b 1
)

call photoshop\Scripts\activate.bat

echo ============================================
echo  STEP 0: Initial Test
echo ============================================
echo.
echo Testing if torch already works...
python -c "import torch; print('SUCCESS')" 2>nul | findstr "SUCCESS" >nul
if not errorlevel 1 (
    echo.
    echo ============================================
    echo  TORCH IS ALREADY WORKING!
    echo ============================================
    echo.
    echo No fix needed. You can run automation.bat
    echo.
    pause
    exit /b 0
)
echo Torch is NOT working. Starting fix process...
echo.

echo ============================================
echo  STEP 1: Update Visual C++ Redistributable
echo ============================================
echo.
echo Downloading latest VC++ Redistributable x64...

powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '%TEMP%\vc_redist.x64.exe' -UseBasicParsing}" 2>nul

if not exist "%TEMP%\vc_redist.x64.exe" (
    echo Download failed! Trying alternative method...
    curl -L -o "%TEMP%\vc_redist.x64.exe" "https://aka.ms/vs/17/release/vc_redist.x64.exe" 2>nul
)

if not exist "%TEMP%\vc_redist.x64.exe" (
    echo.
    echo WARNING: Could not download VC++ Redistributable
    echo Skipping to Step 2...
    goto :step2
)

echo Download complete!
echo Installing VC++ Redistributable (please wait)...
echo.

"%TEMP%\vc_redist.x64.exe" /install /quiet /norestart

timeout /t 5 >nul

echo Installation complete!
echo.

echo ============================================
echo  STEP 1 VERIFICATION
echo ============================================
echo.
echo Testing if torch works now...

python -c "import torch; print('SUCCESS')" 2>nul | findstr "SUCCESS" >nul
if not errorlevel 1 (
    echo.
    echo ============================================
    echo  SUCCESS! VC++ UPDATE FIXED THE ISSUE
    echo ============================================
    echo.
    echo IMPORTANT: Please restart your computer
    echo before running automation.bat
    echo.
    echo (Restart ensures all DLLs are loaded fresh)
    echo.
    pause
    exit /b 0
)

echo Torch still not working after VC++ update.
echo Proceeding to Step 2...
echo.

:step2
echo ============================================
echo  STEP 2: Reinstall PyTorch (CPU Version)
echo ============================================
echo.
echo Uninstalling current torch packages...
echo.

pip uninstall torch torchvision torchaudio -y 2>nul
pip uninstall torch torchvision torchaudio -y 2>nul

echo.
echo Installing PyTorch CPU-only version...
echo (This has fewer dependencies and is more stable)
echo.
echo This may take several minutes, please wait...
echo.

pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

if errorlevel 1 (
    echo.
    echo Primary install failed. Trying alternative...
    pip install torch torchvision
)

echo.
echo ============================================
echo  STEP 2 VERIFICATION
echo ============================================
echo.
echo Testing if torch works now...

python -c "import torch; print('Torch version:', torch.__version__); print('SUCCESS')" 2>&1
python -c "import torch" 2>nul
if not errorlevel 1 (
    echo.
    echo ============================================
    echo  SUCCESS! PYTORCH REINSTALL FIXED IT
    echo ============================================
    echo.
    echo Torch is now working correctly.
    echo You can run automation.bat
    echo.
    echo NOTE: A computer restart is still recommended.
    echo.
    pause
    exit /b 0
)

echo.
echo ============================================
echo  STEP 3: Deep Clean and Reinstall
echo ============================================
echo.
echo Previous attempts failed. Doing a deep clean...
echo.

:: Clear pip cache
pip cache purge 2>nul

:: Uninstall again to be sure
pip uninstall torch torchvision torchaudio -y 2>nul

:: Remove any leftover torch folders
if exist "photoshop\Lib\site-packages\torch" (
    echo Removing leftover torch folder...
    rmdir /s /q "photoshop\Lib\site-packages\torch" 2>nul
)

echo.
echo Reinstalling with fresh download...
echo.

pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

echo.
echo ============================================
echo  FINAL VERIFICATION
echo ============================================
echo.

python -c "import torch; print('Torch version:', torch.__version__)" 2>&1
python -c "import torch" 2>nul
if not errorlevel 1 (
    echo.
    echo ============================================
    echo  SUCCESS! DEEP CLEAN FIXED THE ISSUE
    echo ============================================
    echo.
    echo Please restart your computer, then run
    echo automation.bat
    echo.
    pause
    exit /b 0
)

echo.
echo ============================================
echo  ALL AUTOMATIC FIXES FAILED
echo ============================================
echo.
echo Please try these manual steps:
echo.
echo 1. Restart your computer
echo.
echo 2. Delete the entire 'photoshop' folder in
echo    this directory
echo.
echo 3. Run runOnce.bat as Administrator
echo.
echo 4. If still failing, check:
echo    - Antivirus blocking DLL files
echo    - Windows updates pending
echo    - Disk space available
echo.
echo 5. Send the output of diagnose.bat for
echo    further assistance.
echo.
echo ============================================
pause
exit /b 1
