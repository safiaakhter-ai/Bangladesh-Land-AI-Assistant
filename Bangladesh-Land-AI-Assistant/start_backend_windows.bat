@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 ( echo Python 3 is required. & pause & exit /b 1 )
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 ( echo Failed to install backend dependencies. & pause & exit /b 1 )
if not exist .env copy .env.example .env >nul
.venv\Scripts\python.exe app.py
pause
