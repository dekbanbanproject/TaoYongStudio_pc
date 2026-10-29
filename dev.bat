@echo off
REM ============================================================
REM  TaoYongStudio Desktop V2 - โหมดพัฒนา (React HMR + Tauri)
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist "engine\.venv\Scripts\python.exe" (
  echo กำลังสร้าง Python venv ครั้งแรก...
  python -m venv engine\.venv
  "engine\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
  "engine\.venv\Scripts\python.exe" -m pip install -r "engine\requirements.txt"
)

pushd desktop
call npm run tauri:dev
popd
