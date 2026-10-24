@echo off
chcp 65001 >nul
cd /d "%~dp0"
.venv\Scripts\python -m studio samples
.venv\Scripts\python -m studio batch
echo.
echo Finished. Opening the output folder...
start "" "%~dp0output"
pause
