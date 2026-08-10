@echo off
rem ------------------------------------------------------------------------------
rem make.bat - Build TuFac.exe (Windows) using PyInstaller
rem ------------------------------------------------------------------------------

setlocal
cd /d "%~dp0.."

if not exist venv\Scripts\python.exe (
    echo ERROR: virtual environment not found.
    echo Run .\bin\setup.bat first.
    exit /b 1
)

call venv\Scripts\python.exe -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller not found.
    echo Run .\bin\setup.bat first.
    exit /b 1
)

echo ==^> Removing old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist TuFac.spec del TuFac.spec

echo ==^> Building TuFac...
call venv\Scripts\python.exe -m PyInstaller ^
    --name "TuFac" ^
    --windowed ^
    --onefile ^
    --icon "app\resources\app_icon.ico" ^
    --add-data "app\resources;resources" ^
    --hidden-import "PySide6" ^
    --hidden-import "PySide6.QtCore" ^
    --hidden-import "PySide6.QtGui" ^
    --hidden-import "PySide6.QtWidgets" ^
    --hidden-import "cv2" ^
    --hidden-import "zxingcpp" ^
    --hidden-import "pyotp" ^
    app\tufac.py
if errorlevel 1 goto :error

echo.
echo ==^> Build finished.
echo ==^> Application: dist\TuFac.exe
exit /b 0

:error
echo.
echo ==^> Build failed.
exit /b 1
