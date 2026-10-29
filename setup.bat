@echo off
REM ============================================================
REM  TaoYongStudio Desktop V2 - ติดตั้งครั้งแรก
REM  สร้าง Python venv, ติดตั้ง requirements, ติดตั้ง npm packages
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo [1/4] ตรวจสอบ Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo   ไม่พบ Python - กรุณาติดตั้ง Python 3.11 ขึ้นไปจาก python.org
  pause
  exit /b 1
)

echo [2/4] สร้าง Python virtual environment...
if not exist "engine\.venv\Scripts\python.exe" (
  python -m venv engine\.venv
) else (
  echo   มี .venv อยู่แล้ว - ข้าม
)

echo [3/4] ติดตั้ง Python packages...
"engine\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
"engine\.venv\Scripts\python.exe" -m pip install -r "engine\requirements.txt"

echo [4/4] ติดตั้ง frontend packages...
pushd desktop
call npm install
popd

echo.
echo ============================================================
echo  ติดตั้งเรียบร้อย
echo.
echo  รันโปรแกรม:  double-click TaoYongStudio.bat
echo  โหมด dev:   double-click dev.bat
echo ============================================================
pause
