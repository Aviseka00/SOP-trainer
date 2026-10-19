@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run INSTALL_WINDOWS.bat first. & pause & exit /b 1)
set "SOP_TEST_SPEECH=1"
".venv\Scripts\python.exe" -m unittest discover -s tests -v
pause
