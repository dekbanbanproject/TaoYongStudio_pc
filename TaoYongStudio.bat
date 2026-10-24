@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo TaoYongStudio is not installed yet. Run setup.bat first.
  pause
  exit /b 1
)
start "" .venv\Scripts\pythonw.exe -m studio.gui
