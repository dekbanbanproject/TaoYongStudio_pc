@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs
.venv\Scripts\python -m studio publish auto >> logs\auto_post.log 2>&1
