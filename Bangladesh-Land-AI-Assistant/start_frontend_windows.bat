@echo off
setlocal
cd /d "%~dp0frontend"
where npm >nul 2>&1
if errorlevel 1 ( echo Node.js 20+ is required. & pause & exit /b 1 )
if not exist node_modules call npm ci
if errorlevel 1 ( echo Failed to install frontend dependencies. & pause & exit /b 1 )
call npm run dev
pause
