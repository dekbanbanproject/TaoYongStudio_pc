@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === TaoYongStudio setup ===
set "PY="
py -3.12 -V >nul 2>nul && set "PY=py -3.12"
if not defined PY py -3 -V >nul 2>nul && set "PY=py -3"
if not defined PY python -V >nul 2>nul && set "PY=python"
if not defined PY goto nopython
echo Using %PY%
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
if not exist .venv\Scripts\python.exe goto fail
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Installing optional offline test voice...
.venv\Scripts\python -m pip install espeakng-loader >nul 2>nul
if not exist config.json copy config.example.json config.json >nul
echo.
.venv\Scripts\python -m studio check
echo.
call make_shortcut.bat
echo Setup finished. Open TaoYongStudio from the icon on your Desktop.
pause
exit /b 0
:nopython
echo Python was not found. Installing Python 3.12 with winget...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo Close this window, then double-click setup.bat again.
pause
exit /b 1
:fail
echo.
echo SETUP FAILED - send a screenshot of this window to Claude.
pause
exit /b 1
