@echo off
schtasks /Delete /F /TN "KidsStudio Daily Batch"
for /L %%i in (1,1,8) do schtasks /Delete /F /TN "KidsStudio Auto Post %%i" >nul 2>nul
echo TaoYongStudio automatic render and posting removed.
pause
