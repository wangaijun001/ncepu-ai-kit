@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

echo ============================================================
echo   NCEPU AI Model - Local Proxy
echo ============================================================
echo.
echo   Purpose: convert the standard OpenAI path
echo              /v1/chat/completions
echo            into the school endpoint
echo              /api/chat/completions
echo.
echo   Use this when a tool keeps returning 405 Method Not Allowed.
echo   Then set the tool's Base URL to:  http://127.0.0.1:8788/v1
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [ERROR] Python not found on this computer.
  echo   Install Python 3.9+ from https://www.python.org/downloads/
  echo   and check "Add Python to PATH" during setup.
  echo.
  pause
  exit /b 1
)

%PY% -c "import requests" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing dependency: requests
  %PY% -m pip install requests
  echo.
)

if not exist "api_key.txt" (
  echo [ERROR] api_key.txt not found.
  echo   Put your sk- key on line 1 of api_key.txt,
  echo   or run check-ncepu-ai.bat first to create it.
  echo.
  pause
  exit /b 1
)

%PY% ncepu_proxy.py %*
echo.
pause
