@echo off
cd /d "%~dp0"

set "CHROME_PATH="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_PATH if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if not defined CHROME_PATH (
  echo Chrome was not found.
  echo Open kiosk.html manually in your browser instead.
  pause
  exit /b 1
)

start "" "%CHROME_PATH%" --kiosk "%~dp0kiosk.html"
