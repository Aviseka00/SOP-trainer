@echo off
setlocal
cd /d "%~dp0"
echo SOP Trainer AI - local environment setup
echo Installs Python packages into .venv. No AI models or unrelated programs are downloaded.
if exist ".venv\Scripts\python.exe" goto install
set "SOP_PY=python"
where py >nul 2>nul
if errorlevel 1 goto create
py -3.11 -c "import sys" >nul 2>nul
if errorlevel 1 goto create
set "SOP_PY=py -3.11"
:create
%SOP_PY% -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10 or newer required'" || goto fail
%SOP_PY% -m venv .venv || goto fail
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto fail
".venv\Scripts\python.exe" -m pip check || goto fail
".venv\Scripts\python.exe" -m sop_studio.diagnostics
echo.
echo Setup complete. Launch START_WINDOWS.bat. No administrator access is required.
exit /b 0
:fail
echo.
echo Setup failed. Check Python installation and internet access. See docs\TROUBLESHOOTING.md.
pause
exit /b 1
