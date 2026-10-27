@echo off
rem One-time setup on Windows. Creates the project's own Python in .venv and installs
rem everything into it. Nothing is installed into your system Python.
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv ...
  %PY% -m venv .venv || exit /b 1
)

echo Installing packages. This takes a few minutes the first time ...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q || exit /b 1

if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  echo Created .env. Open it and paste your API key after ANTHROPIC_API_KEY=
)
if not exist "data\sample\customer_churn.csv" (
  ".venv\Scripts\python.exe" scripts\make_sample_data.py
)

echo.
echo Setup is complete. Start the app with:   .\run.bat
endlocal
