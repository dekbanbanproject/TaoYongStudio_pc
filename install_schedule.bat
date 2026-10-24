@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === TaoYongStudio: daily auto run ===
echo.
echo Type the time Windows should render clips every day (24-hour, HH:MM).
echo Example: 07:00  or  13:30  or  20:00
echo Tip: keep it at least 30 minutes after the time Claude writes the scripts (06:22).
echo.
set "T="
set /p "T=Time [press Enter for 07:00]: "
if "%T%"=="" set "T=07:00"
echo %T%| findstr /r "^[0-2][0-9]:[0-5][0-9]$" >nul
if errorlevel 1 goto badtime
if not exist logs mkdir logs
schtasks /Create /F /TN "KidsStudio Daily Batch" /SC DAILY /ST %T% /TR "\"%~dp0run_batch_auto.bat\""
if errorlevel 1 goto fail
echo.
echo DONE. Windows will render all scripts in scripts\inbox every day at %T%.
echo To change the time: run this file again. To stop: run uninstall_schedule.bat
pause
exit /b 0
:badtime
echo.
echo "%T%" is not a valid time. Use HH:MM, for example 07:00
pause
exit /b 1
:fail
echo.
echo FAILED - send a screenshot of this window to Claude.
pause
exit /b 1
