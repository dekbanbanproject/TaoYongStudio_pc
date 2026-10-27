@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build TaoYongStudio Installer
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\build_installer.ps1"
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check the error message above.
    pause
    exit /b 1
)
echo.
pause

