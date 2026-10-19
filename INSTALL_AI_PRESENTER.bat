@echo off
setlocal
cd /d "%~dp0"
echo Optional AI presenter setup: isolated CPU runtime, official source and roughly 1 GB of model weights.
echo Allow several GB of disk space. No paid service is used. Core app environment stays separate.
if not exist ".venv\Scripts\python.exe" (echo Run INSTALL_WINDOWS.bat first. & exit /b 1)
if exist ".avatar_venv\Scripts\python.exe" goto source
py -3.10 -c "import sys" >nul 2>nul
if errorlevel 1 goto corepython
py -3.10 -m venv .avatar_venv || goto fail
goto source
:corepython
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3,10), 'Install Python 3.10 for the optional presenter environment'" || goto fail
".venv\Scripts\python.exe" -m venv .avatar_venv
if errorlevel 1 goto fail
:source
".avatar_venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3,10), 'Presenter dependencies require Python 3.10 in this release'" || goto fail
".venv\Scripts\python.exe" scripts\download_presenter_source.py || goto fail
".avatar_venv\Scripts\python.exe" -m pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cpu || goto fail
".avatar_venv\Scripts\python.exe" -m pip install -r requirements-avatar.txt || goto fail
".avatar_venv\Scripts\python.exe" scripts\verify_presenter_runtime.py || goto fail
".venv\Scripts\python.exe" scripts\download_presenter_models.py --download || goto fail
echo Setup files are installed. Use Presenter studio to render and inspect an actual speaking preview.
exit /b 0
:fail
echo Presenter setup failed. The core SOP app remains available. See docs\PRESENTER.md.
pause
exit /b 1
