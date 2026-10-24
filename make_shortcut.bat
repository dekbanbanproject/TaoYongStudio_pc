@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'TaoYongStudio.lnk')); $s.TargetPath='%~dp0.venv\Scripts\pythonw.exe'; $s.Arguments='-m studio.gui'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0studio\app.ico'; $s.Description='TaoYongStudio'; $s.Save(); Write-Output ('Shortcut created on ' + $d)"
