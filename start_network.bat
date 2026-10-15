@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
echo Starting COMSOL small model web app in LAN mode...
echo.
echo This binds the app to 0.0.0.0 so other devices on the same network can connect.
echo If Windows Firewall asks for permission, allow Python on Private networks only.
echo.
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%~dp0..\runtime\python312\python.exe"
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python 3.12 runtime was not found. Run rebuild_environment.bat first.
    pause
    exit /b 1
)
"%PYTHON_EXE%" scripts\start_local_service.py --lan --port 8765 --wait-seconds 30
pause
