@echo off
setlocal enabledelayedexpansion

REM Load variables from .env file
for /f "usebackq tokens=1,2 delims==" %%i in (`.env`) do (
    set %%i=%%j
)

REM Example usage
echo DB_HOST is %DB_HOST%
echo DB_USER is %DB_USER%

endlocal