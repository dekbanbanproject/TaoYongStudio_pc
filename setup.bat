@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title TaoYongStudio installer
echo ==========================================
echo   TaoYongStudio installer
echo ==========================================
echo   Folder: %~dp0
echo.
rem  setup.bat /yes   = answer yes to every question (unattended install)
set "ASSUME_YES="
if /i "%~1"=="/yes" set "ASSUME_YES=1"

rem ---------- 1. Python ----------
echo [1/6] Looking for Python...
set "PY="
for %%V in (3.12 3.13 3.11 3.10) do (
  if not defined PY (
    py -%%V -V >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY py -3 -V >nul 2>nul && set "PY=py -3"
if not defined PY python -V >nul 2>nul && set "PY=python"
if not defined PY goto nopython
echo       Using %PY%

rem ---------- 2. virtual environment ----------
echo [2/6] Creating virtual environment (.venv)...
if exist .venv\Scripts\python.exe goto venvok
%PY% -m venv .venv
if not exist .venv\Scripts\python.exe goto fail
:venvok

rem ---------- 3. packages ----------
echo [3/6] Installing Python packages (this can take a few minutes)...
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo       Installing optional offline test voice...
.venv\Scripts\python -m pip install espeakng-loader >nul 2>nul

rem ---------- 4. Blender (needed only by the 3D engines) ----------
echo [4/6] Checking Blender 4.2 LTS (used by Chibi 3D / Cinematic 3D / Toy Ad 3D)...
call :find_blender
if defined BLENDER goto blenderok
echo       Blender is not installed. The normal 2D clips work without it.
set "ANS=N"
if defined ASSUME_YES (set "ANS=Y") else set /p "ANS=      Install Blender 4.2 LTS now with winget? [y/N]: "
if /i not "%ANS%"=="Y" goto blenderskip
winget install -e --id BlenderFoundation.Blender.LTS.4.2 --accept-package-agreements --accept-source-agreements
call :find_blender
if not defined BLENDER echo       Blender install did not finish. You can run setup.bat again later.
:blenderok
if defined BLENDER echo       Blender: %BLENDER%
:blenderskip

rem ---------- 5. folders + config ----------
echo [5/6] Preparing folders and settings...
for %%D in (scripts\inbox scripts\done scripts\failed output logs cache secrets plans\requests plans\results) do (
  if not exist %%D mkdir %%D
)
if not exist config.json copy config.example.json config.json >nul

rem ---------- 6. self-check + desktop shortcut ----------
echo [6/6] Running self-check...
echo.
.venv\Scripts\python -m studio check
echo.
call "%~dp0make_shortcut.bat"
echo.
echo ==========================================
echo   Setup finished.
echo   Open TaoYongStudio from the icon on your Desktop.
echo   Optional: run render_samples.bat to make 2 sample clips.
echo ==========================================
if not defined ASSUME_YES pause
exit /b 0

:nopython
echo       Python was not found. Installing Python 3.12 with winget...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo Close this window, then double-click setup.bat again.
if not defined ASSUME_YES pause
exit /b 1

:fail
echo.
echo SETUP FAILED - send a screenshot of this window to Claude.
if not defined ASSUME_YES pause
exit /b 1

:find_blender
set "BLENDER="
for %%P in (
  "%ProgramFiles%\Blender Foundation\Blender 4.2\blender.exe"
  "%ProgramFiles%\Blender Foundation\Blender\blender.exe"
) do if exist %%P set "BLENDER=%%~P"
if not defined BLENDER for /f "delims=" %%B in ('where blender 2^>nul') do if not defined BLENDER set "BLENDER=%%B"
exit /b 0
