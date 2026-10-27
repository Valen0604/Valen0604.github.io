@echo off
rem Start the app on Windows. Run setup.bat once first.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The project is not set up yet. Run setup.bat first.
  exit /b 1
)
".venv\Scripts\python.exe" -m app %*
endlocal
