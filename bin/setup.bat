@echo off
rem ------------------------------------------------------------------------------
rem setup.bat - Windows Python environment, venv, packages
rem ------------------------------------------------------------------------------

setlocal
cd /d "%~dp0.."

rem --- 1. Check Python ---

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on PATH.
    echo Install Python 3.11+ from https://www.python.org/downloads/
    exit /b 1
)

rem --- 2. Remove old venv ---

echo ==^> Removing old venv...
if exist venv rmdir /s /q venv

rem --- 3. Create new venv ---

echo ==^> Creating new venv...
python -m venv venv
if errorlevel 1 goto :error

echo ==^> Active Python:
call venv\Scripts\python.exe --version

rem --- 4. Upgrade packaging tools ---

echo ==^> Upgrading pip, setuptools, wheel...
call venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error

rem --- 5. Install required packages ---

echo ==^> Installing required packages...
call venv\Scripts\python.exe -m pip install PySide6 pyinstaller qrcode[pil] opencv-python zxing-cpp pyotp cryptography pytest
if errorlevel 1 goto :error

echo.
echo ==^> Setup complete.
echo ==^> Run .\bin\tufac.bat to start TuFac, or .\bin\make.bat to build.
exit /b 0

:error
echo.
echo ==^> Setup failed.
exit /b 1
