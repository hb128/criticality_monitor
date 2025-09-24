@echo off
setlocal enabledelayedexpansion

REM Criticality Monitor Server Management Script for Windows
REM Usage: manage.bat [start|stop|restart|status|logs|update]

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

REM Colors for output (using echo with special characters)
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM Functions for colored output
:log
echo %BLUE%[%date% %time%]%NC% %~1
goto :eof

:error
echo %RED%[ERROR]%NC% %~1 >&2
goto :eof

:success
echo %GREEN%[SUCCESS]%NC% %~1
goto :eof

:warning
echo %YELLOW%[WARNING]%NC% %~1
goto :eof

REM Check if Docker and Docker Compose are available
:check_dependencies
docker --version >nul 2>&1
if errorlevel 1 (
    call :error "Docker is not installed or not in PATH"
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        call :error "Docker Compose is not installed or not in PATH"
        exit /b 1
    )
    set "COMPOSE_CMD=docker compose"
) else (
    set "COMPOSE_CMD=docker-compose"
)
goto :eof

REM Start all services
:start_services
call :log "Starting Criticality Monitor services..."

cd /d "%SCRIPT_DIR%"

REM Create necessary directories
if not exist "%PROJECT_DIR%\cm_logs\automated" mkdir "%PROJECT_DIR%\cm_logs\automated"
if not exist "%PROJECT_DIR%\cm_logs\hamburg" mkdir "%PROJECT_DIR%\cm_logs\hamburg"
if not exist "%PROJECT_DIR%\cm_logs\berlin" mkdir "%PROJECT_DIR%\cm_logs\berlin"
if not exist "%PROJECT_DIR%\site\hamburg" mkdir "%PROJECT_DIR%\site\hamburg"
if not exist "%PROJECT_DIR%\site\berlin" mkdir "%PROJECT_DIR%\site\berlin"
if not exist "%PROJECT_DIR%\site\main" mkdir "%PROJECT_DIR%\site\main"
if not exist "%PROJECT_DIR%\config" mkdir "%PROJECT_DIR%\config"
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

REM Build and start services
%COMPOSE_CMD% build
%COMPOSE_CMD% up -d

call :success "Services started successfully"

REM Show status
call :show_status

REM Show access information
echo.
call :log "Access information:"
echo   Web interface: http://localhost:8080
echo   Main leaderboard: http://localhost:8080/
echo   Hamburg site: http://localhost:8080/hamburg/
echo   Berlin site: http://localhost:8080/berlin/
echo   Health check: http://localhost:8080/health
goto :eof

REM Stop all services
:stop_services
call :log "Stopping Criticality Monitor services..."

cd /d "%SCRIPT_DIR%"
%COMPOSE_CMD% down

call :success "Services stopped successfully"
goto :eof

REM Restart all services
:restart_services
call :log "Restarting Criticality Monitor services..."
call :stop_services
timeout /t 2 /nobreak >nul
call :start_services
goto :eof

REM Show service status
:show_status
call :log "Service Status:"

cd /d "%SCRIPT_DIR%"
%COMPOSE_CMD% ps

echo.
call :log "Container health:"
docker ps --filter "name=cm-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
goto :eof

REM Show logs for all or specific service
:show_logs
cd /d "%SCRIPT_DIR%"

if "%~1"=="" (
    call :log "Showing logs for all services (press Ctrl+C to exit):"
    %COMPOSE_CMD% logs -f
) else (
    call :log "Showing logs for service: %~1"
    %COMPOSE_CMD% logs -f "%~1"
)
goto :eof

REM Update and rebuild services
:update_services
call :log "Updating Criticality Monitor services..."

cd /d "%SCRIPT_DIR%"

REM Pull latest changes (if this is a git repo)
if exist "%PROJECT_DIR%\.git" (
    call :log "Pulling latest changes from git..."
    cd /d "%PROJECT_DIR%"
    git pull
    cd /d "%SCRIPT_DIR%"
)

REM Rebuild and restart
%COMPOSE_CMD% build --no-cache
%COMPOSE_CMD% up -d

call :success "Services updated successfully"
call :show_status
goto :eof

REM Show disk usage
:show_disk_usage
call :log "Disk usage for Criticality Monitor data:"

echo Log files:
if exist "%PROJECT_DIR%\cm_logs" (
    dir "%PROJECT_DIR%\cm_logs" /s /-c | find "bytes"
) else (
    echo   No log directory found
)

echo Generated sites:
if exist "%PROJECT_DIR%\site" (
    dir "%PROJECT_DIR%\site" /s /-c | find "bytes"
) else (
    echo   No site directory found
)

echo Docker volumes:
docker system df
goto :eof

REM Backup data
:backup_data
set "backup_dir=%~1"
if "%backup_dir%"=="" (
    for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "backup_dir=backups\%%c%%a%%b"
    for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "backup_dir=!backup_dir!_%%a%%b"
)

call :log "Creating backup to: %backup_dir%"

if not exist "%backup_dir%" mkdir "%backup_dir%"

REM Backup logs and sites
if exist "%PROJECT_DIR%\cm_logs" (
    xcopy "%PROJECT_DIR%\cm_logs" "%backup_dir%\cm_logs\" /e /i /q
)

if exist "%PROJECT_DIR%\site" (
    xcopy "%PROJECT_DIR%\site" "%backup_dir%\site\" /e /i /q
)

REM Backup configuration
if exist "%PROJECT_DIR%\config" (
    xcopy "%PROJECT_DIR%\config" "%backup_dir%\config\" /e /i /q
)

call :success "Backup created at: %backup_dir%"
goto :eof

REM Show help
:show_help
echo Criticality Monitor Server Management Script for Windows
echo.
echo Usage: %~nx0 ^<command^> [options]
echo.
echo Commands:
echo   start                 Start all services
echo   stop                  Stop all services
echo   restart               Restart all services
echo   status                Show service status
echo   logs [service]        Show logs (all services or specific service)
echo   update                Update and rebuild services
echo   disk                  Show disk usage
echo   backup [dir]          Backup data to directory
echo   help                  Show this help
echo.
echo Services:
echo   automated-logger      Location logging service
echo   batch-processor-hamburg  Hamburg data processor
echo   batch-processor-berlin   Berlin data processor
echo   site-builder          Website builder
echo   web-server            Nginx web server
echo   monitoring            Service monitoring
echo.
echo Examples:
echo   %~nx0 start              # Start all services
echo   %~nx0 logs web-server    # Show web server logs
echo   %~nx0 backup C:\backup\cm  # Backup to specific directory
goto :eof

REM Main script logic
call :check_dependencies

set "command=%~1"
if "%command%"=="" set "command=help"

if "%command%"=="start" (
    call :start_services
) else if "%command%"=="stop" (
    call :stop_services
) else if "%command%"=="restart" (
    call :restart_services
) else if "%command%"=="status" (
    call :show_status
) else if "%command%"=="logs" (
    call :show_logs "%~2"
) else if "%command%"=="update" (
    call :update_services
) else if "%command%"=="disk" (
    call :show_disk_usage
) else if "%command%"=="backup" (
    call :backup_data "%~2"
) else if "%command%"=="help" (
    call :show_help
) else if "%command%"=="--help" (
    call :show_help
) else if "%command%"=="-h" (
    call :show_help
) else (
    call :error "Unknown command: %command%"
    echo.
    call :show_help
    exit /b 1
)