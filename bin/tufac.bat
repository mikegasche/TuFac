@echo off
rem ------------------------------------------------------------------------------
rem tufac.bat - Run TuFac (Windows)
rem ------------------------------------------------------------------------------

cd /d "%~dp0.."

if not exist venv\Scripts\python.exe (
    echo ERROR: virtual environment not found.
    echo Run .\bin\setup.bat first.
    exit /b 1
)

call venv\Scripts\python.exe app\tufac.py
