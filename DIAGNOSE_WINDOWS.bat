@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run INSTALL_WINDOWS.bat first. & pause & exit /b 1)
".venv\Scripts\python.exe" -m sop_studio.diagnostics
".venv\Scripts\python.exe" -m pip check
pause
