@echo off
REM ============================================================
REM  TaoYongStudio Desktop V2 - เปิดโปรแกรม
REM  ถ้ายังไม่ได้ build ให้ build ก่อน แล้วเปิดไฟล์ตัวโปรแกรม
REM ============================================================
setlocal
cd /d "%~dp0"

set EXE=desktop\src-tauri\target\release\taoyongstudio.exe
set INSTALLED=%LOCALAPPDATA%\TaoYongStudio\TaoYongStudio.exe

if exist "%EXE%" (
  start "" "%EXE%"
  exit /b 0
)
if exist "%INSTALLED%" (
  start "" "%INSTALLED%"
  exit /b 0
)

echo  ยังไม่พบโปรแกรมที่ build แล้ว - กำลัง build...
pushd desktop
call npm run tauri:build
popd
if exist "%EXE%" (
  start "" "%EXE%"
) else (
  echo build ไม่สำเร็จ - ดูข้อความด้านบน
  pause
)
