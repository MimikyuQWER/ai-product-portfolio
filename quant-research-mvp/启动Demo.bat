@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ============================================================
echo  AI Quant Research System - One-click Start (Windows)
echo ============================================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY ( where python3 >nul 2>nul && set "PY=python3" )

if not defined PY goto NOPY

echo [1/3] Python detected: %PY%

if not exist ".venv\Scripts\python.exe" goto MAKEVENV
goto CHECKDEPS

:MAKEVENV
echo [2/3] First run: creating venv and installing deps, 1 to 2 minutes
%PY% -m venv .venv
if errorlevel 1 goto VENVERR
goto INSTALL

:CHECKDEPS
call ".venv\Scripts\activate.bat"
.venv\Scripts\python.exe -c "import numpy, pandas, scipy, yaml" >nul 2>&1
if errorlevel 1 (
  echo [2/3] Dependencies missing, rebuilding venv and installing, 1 to 2 minutes
  rmdir /s /q .venv
  %PY% -m venv .venv
  if errorlevel 1 goto VENVERR
  goto INSTALL
) else (
  echo [2/3] Dependencies already satisfied, skipping install.
)
goto RUNSVR

:INSTALL
call ".venv\Scripts\activate.bat"
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto PIPERR
echo       Dependencies installed.
goto RUNSVR

:VENVERR
echo [Error] Failed to create venv. Check that Python is installed correctly.
pause
exit /b 1

:PIPERR
echo [Error] Dependency install failed. Check your network and retry.
pause
exit /b 1

:RUNSVR
echo [3/3] Starting local server in this window. Keep it open.
echo        Open browser: http://127.0.0.1:8765/index.html
echo        Press Ctrl+C to stop the server.
echo.
call ".venv\Scripts\activate.bat"
ping -n 5 127.0.0.1 >nul
start "" http://127.0.0.1:8765/index.html
.venv\Scripts\python.exe -m backend.run_server
echo.
echo [Server stopped] Press any key to close this window.
pause
goto :EOF

:NOPY
echo [Hint] Python was not found on this machine.
echo.
echo Option A - View the UI without installing anything, recommended
echo   Double-click site\research.html or site\index.html
echo   The pages contain built-in demo data and work fully offline.
echo.
echo Option B - Install Python 3.11+ from https://www.python.org
echo   During install, check "Add python.exe to PATH", then re-run.
echo.
pause
exit /b 1
