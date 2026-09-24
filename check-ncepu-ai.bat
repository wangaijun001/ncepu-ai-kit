@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

echo ============================================================
echo   NCEPU AI Model - Connection Self Check
echo ============================================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [ERROR] Python not found on this computer.
  echo.
  echo   Please install Python 3.9+ from:
  echo     https://www.python.org/downloads/
  echo   IMPORTANT: check "Add Python to PATH" during setup.
  echo.
  pause
  exit /b 1
)
echo [OK] Using Python: %PY%
echo.

%PY% -c "import requests" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing dependency: requests
  %PY% -m pip install requests
  echo.
)

if not exist "api_key.txt" (
  > api_key.txt echo PASTE_YOUR_KEY_HERE
  echo ============================================================
  echo  First run: api_key.txt has been created and opened.
  echo.
  echo  Paste your API key on LINE 1, save, and close Notepad.
  echo  Get a key at: http://202.204.64.234:8080
  echo    avatar - Settings - Account - API Keys - Create
  echo ============================================================
  echo.
  start "" notepad "api_key.txt"
  echo After saving the key, press any key to run the self check...
  pause >nul
  echo.
)

%PY% "test_ncepu_ai.py" %*
echo.
pause
