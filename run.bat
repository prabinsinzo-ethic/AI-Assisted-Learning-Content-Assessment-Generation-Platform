@echo off
setlocal
set "PORT=8001"
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"

if /I "%~1"=="stop" goto :stop
if /I "%~1"=="restart" goto :restart
if /I "%~1"=="status" goto :status
if not "%~1"=="" if not "%~1"=="start" (
    echo Usage: %~nx0 [start^|stop^|restart^|status]
    exit /b 1
)

:start
cd /d "%BACKEND%"
echo Starting AI Learning Content Platform on http://127.0.0.1:%PORT% ...
start "AI Platform" cmd /k "python -m uvicorn app.main:app --reload --port %PORT%"
echo Server launched in a new window.
goto :end

:stop
echo Stopping server on port %PORT% ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo Done.
goto :end

:restart
call :stop
timeout /t 2 /nobreak >nul
goto :start

:status
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul
if errorlevel 1 (echo Server is NOT running on port %PORT%.) else (echo Server is running on port %PORT%.)
goto :end

:end
endlocal