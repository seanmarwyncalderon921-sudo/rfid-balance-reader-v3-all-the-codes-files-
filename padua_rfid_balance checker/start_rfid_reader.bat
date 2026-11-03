@echo off
cd /d "%~dp0"

REM If python is not in PATH, replace this with the full path to your Python executable.
set "PYTHON_EXE=python"

REM Optional: uncomment and set a specific port if auto-detect fails.
REM set "ARDUINO_PORT=COM7"

where %PYTHON_EXE% >nul 2>nul
if errorlevel 1 (
  echo ERROR_PYTHON_NOT_FOUND: Python was not found in PATH.
  echo Open a terminal in VS Code and run: where python
  echo Then replace PYTHON_EXE in this file with the full path to python.exe
  pause
  exit /b 10
)

%PYTHON_EXE% rfid_balance_reader.py
if errorlevel 1 (
  echo.
  echo ERROR_ARDUINO_START_FAILED: The RFID reader could not start.
  echo Fix the COM port in Device Manager, then set ARDUINO_PORT in this file.
  echo Example: set "ARDUINO_PORT=COM7"
  pause
  exit /b 20
)
