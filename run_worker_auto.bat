@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs
.venv\Scripts\python -m studio worker-run >> logs\worker_auto.log 2>&1
