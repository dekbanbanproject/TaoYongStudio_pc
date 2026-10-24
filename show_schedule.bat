@echo off
chcp 65001 >nul
schtasks /Query /TN "KidsStudio Daily Batch" /V /FO LIST | findstr /i "TaskName Next Status Start"
pause
