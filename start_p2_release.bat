@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%~dp0..\runtime\python312\python.exe"
if not exist "%PYTHON_EXE%" (
  echo ERROR: Python 3.12 runtime was not found.
  exit /b 1
)
set "PYTHONPATH=%~dp0src"
"%PYTHON_EXE%" scripts\run_p2_migration_acceptance.py
if errorlevel 1 (
  echo ERROR: P2 migration preflight failed. See generated\p2\migration_acceptance.json
  pause
  exit /b 1
)
call start_windows.bat
endlocal
