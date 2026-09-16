@echo off
REM ============================================================================
REM Ravenclaw - double-click launcher
REM
REM Starts the email bridge in a console window that stays open so you can
REM read the log. Press Ctrl+C in the window to stop the bridge.
REM
REM A Desktop shortcut usually points here. Safe to run directly too.
REM ============================================================================

title Ravenclaw Email Bridge

REM Always run from the script's own folder: the inbox, outbox and log files
REM are opened by relative path, so the working directory decides where they land.
cd /d "%~dp0"

echo ==================================================
echo   RAVENCLAW EMAIL BRIDGE
echo ==================================================
echo   Folder: %CD%
echo.

REM --- Python present? ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on your PATH.
    echo         Install Python 3.10+ and tick "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

REM --- Config present? ---
if not exist ".env" (
    echo [ERROR] No .env file in this folder.
    echo         Copy .env.example to .env and fill in your mail settings.
    echo.
    pause
    exit /b 1
)

REM --- Already running? Starting a second copy just fails on the bound port. ---
netstat -ano | findstr /R /C:"127.0.0.1:5002 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Something is already listening on port 5002.
    echo        Ravenclaw may already be running in another window.
    echo.
    choice /C YN /M "Start anyway"
    if errorlevel 2 exit /b 0
    echo.
)

echo Starting... press Ctrl+C in this window to stop.
echo.

python ravenclaw.py

REM Reached on clean shutdown or on a crash - keep the window open either way
REM so the reason is readable rather than flashing past.
echo.
echo ==================================================
if errorlevel 1 (
    echo   Ravenclaw exited with an error ^(code %errorlevel%^).
    echo   Check the messages above and ravenclaw.log.
) else (
    echo   Ravenclaw stopped.
)
echo ==================================================
echo.
pause
