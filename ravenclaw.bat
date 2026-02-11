@echo off
REM ============================================================================
REM Ravenclaw Email Bridge - Windows Batch Script
REM ============================================================================
REM Usage:
REM   ravenclaw.bat [command]
REM
REM Commands:
REM   all       - Start all components
REM   bridge    - Start email bridge only
REM   bot       - Start Discord bot only
REM   scheduler - Start scheduler only
REM   check     - Trigger manual email check
REM   inbox     - View all received emails
REM   unread    - View unread emails
REM   email     - View specific email (usage: ravenclaw.bat email <id>)
REM   status    - Check bridge status
REM   stats     - View statistics
REM   send      - Send email (usage: ravenclaw.bat send to@domain.com "Subject" "Body")
REM   install   - Install dependencies
REM   help      - Show this help
REM
REM Requirements:
REM   - Python 3.8+
REM   - pip install requests flask discord.py
REM ============================================================================

setlocal EnableDelayedExpansion

REM Set default command
set COMMAND=%~1

REM Load .env file
for /f "usebackq tokens=1,* delims==" %%a in (.env) do (
    if "%%a"=="DOMAIN_FILTER" set DOMAIN_FILTER=%%b
    if "%%a"=="BRIDGE_PORT" set BRIDGE_PORT=%%b
)

REM Set defaults
if "%DOMAIN_FILTER%"=="" set DOMAIN_FILTER=sapphire.co
if "%BRIDGE_PORT%"=="" set BRIDGE_PORT=5002

REM Display help
if "%COMMAND%"=="" set COMMAND=help
if "%COMMAND%"=="help" (
    echo =================================================================
    echo   RAVENCLAW EMAIL BRIDGE - Windows Batch Script
    echo =================================================================
    echo.
    echo USAGE:
    echo   ravenclaw.bat [command]
    echo.
    echo COMMANDS:
    echo   all       - Start all components
    echo   bridge    - Start email bridge only
    echo   bot       - Start Discord bot only
    echo   scheduler - Start scheduler only
    echo   check     - Trigger manual email check
    echo   inbox     - View all received emails
    echo   unread    - View unread emails
    echo   email     - View specific email
    echo   status    - Check bridge status
    echo   stats     - View statistics
    echo   send      - Send email
    echo   install   - Install dependencies
    echo   help      - Show this help
    echo.
    echo FILES:
    echo   ravenclaw_inbox.json - Received emails (JSON)
    echo   ravenclaw.log        - Logs
    echo.
    echo ENVIRONMENT VARIABLES (.env):
    echo   DOMAIN_FILTER        - Allowed domains (default: sapphire.co)
    echo   BRIDGE_POLL_INTERVAL - Minutes between checks (default: 30)
    echo.
    echo EXAMPLES:
    echo   ravenclaw.bat all
    echo   ravenclaw.bat bridge
    echo   ravenclaw.bat check
    echo   ravenclaw.bat inbox
    echo   ravenclaw.bat unread
    echo   ravenclaw.bat status
    echo   ravenclaw.bat stats
    echo   ravenclaw.bat send user@sapphire.co "Hello" "Test message"
    echo   ravenclaw.bat help
    echo.
    echo =================================================================
    exit /b 0
)

REM Install dependencies
if "%COMMAND%"=="install" (
    echo [RAVENCLAW] Installing dependencies...
    pip install requests flask discord.py
    echo [RAVENCLAW] Dependencies installed.
    exit /b 0
)

REM Start all components
if "%COMMAND%"=="all" (
    echo [RAVENCLAW] Starting all components...
    echo [RAVENCLAW] Press Ctrl+C to stop all.
    echo.
    start "Ravenclaw Bridge" /MIN cmd /c "python ravenclaw.py"
    start "Ravenclaw Bot" /MIN cmd /c "python ravenclaw-bot.py"
    start "Ravenclaw Scheduler" /MIN cmd /c "python ravenclaw-scheduler.py"
    echo [RAVENCLAW] All components started!
    exit /b 0
)

REM Start email bridge
if "%COMMAND%"=="bridge" (
    echo [RAVENCLAW] Starting email bridge...
    python ravenclaw.py
    exit /b 0
)

REM Start Discord bot
if "%COMMAND%"=="bot" (
    echo [RAVENCLAW] Starting Discord bot...
    python ravenclaw-bot.py
    exit /b 0
)

REM Start scheduler
if "%COMMAND%"=="scheduler" (
    echo [RAVENCLAW] Starting scheduler...
    python ravenclaw-scheduler.py
    exit /b 0
)

REM Trigger email check
if "%COMMAND%"=="check" (
    echo [RAVENCLAW] Checking emails...
    curl -s -X POST http://localhost:%BRIDGE_PORT%/check
    echo.
    echo [RAVENCLAW] Check triggered.
    exit /b 0
)

REM View all received emails (JSON)
if "%COMMAND%"=="inbox" (
    echo [RAVENCLAW] All received emails:
    curl -s http://localhost:%BRIDGE_PORT%/inbox
    echo.
    exit /b 0
)

REM View unread emails
if "%COMMAND%"=="unread" (
    echo [RAVENCLAW] Unread emails:
    curl -s http://localhost:%BRIDGE_PORT%/unread
    echo.
    exit /b 0
)

REM View specific email
if "%COMMAND%"=="email" (
    set EMAIL_ID=%~2
    if "%EMAIL_ID%"=="" (
        echo [ERROR] Missing email ID.
        echo Usage: ravenclaw.bat email ^<id^>
        exit /b 1
    )
    echo [RAVENCLAW] Email details:
    curl -s http://localhost:%BRIDGE_PORT%/inbox/%EMAIL_ID%
    echo.
    exit /b 0
)

REM Check bridge status
if "%COMMAND%"=="status" (
    echo [RAVENCLAW] Bridge status:
    curl -s http://localhost:%BRIDGE_PORT%/health
    echo.
    exit /b 0
)

REM View statistics
if "%COMMAND%"=="stats" (
    echo [RAVENCLAW] Statistics:
    curl -s http://localhost:%BRIDGE_PORT%/stats
    echo.
    exit /b 0
)

REM Send email
if "%COMMAND%"=="send" (
    set TO=%~2
    set SUBJECT=%~3
    set BODY=%~4
    if "%TO%"=="" (
        echo [ERROR] Missing required parameters.
        echo Usage: ravenclaw.bat send to^@domain.com "Subject" "Body"
        exit /b 1
    )
    echo [RAVENCLAW] Sending email to %TO%...
    curl -s -X POST http://localhost:%BRIDGE_PORT%/send -H "Content-Type: application/json" -d "{\"to\":\"%TO%\",\"subject\":\"%SUBJECT%\",\"body\":\"%BODY%\"}"
    echo.
    echo [RAVENCLAW] Email sent.
    exit /b 0
)

REM Unknown command
echo [ERROR] Unknown command: %COMMAND%
echo Run 'ravenclaw.bat help' for usage.
exit /b 1
