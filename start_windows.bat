@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%~dp0..\runtime\python312\python.exe"
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python 3.12 runtime was not found. Run rebuild_environment.bat first.
    exit /b 1
)
echo Starting or reusing the COMSOL small model web service...
echo The first cold start may take 30-60 seconds. Progress will be shown below.
"%PYTHON_EXE%" -u "%~dp0scripts\start_local_service.py" --host 127.0.0.1 --port 8880 --with-worker --with-dac-p0-intake --ensure-comsol-server --open --wait-seconds 90
if errorlevel 1 (
    echo.
    echo ERROR: The local web service did not start.
    echo See generated\training_runs\web_startup.log for details.
    pause
    exit /b 1
)
echo Service is ready at http://127.0.0.1:8880/
echo DAC P0 intake is ready at http://127.0.0.1:8891/
endlocal
