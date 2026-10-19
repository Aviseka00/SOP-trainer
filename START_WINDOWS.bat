@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto start
call INSTALL_WINDOWS.bat
if errorlevel 1 exit /b 1
:start
".venv\Scripts\python.exe" -c "import streamlit, PIL, imageio_ffmpeg" >nul 2>nul
if errorlevel 1 (echo Dependencies are missing. Run INSTALL_WINDOWS.bat. & pause & exit /b 1)
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
pause
