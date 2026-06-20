@echo off
:: ============================================================
:: run_tracker.bat
:: Runs tracker.py, then fix_chart_color.py if a new month
:: sheet was created. Schedule THIS file in Task Scheduler
:: instead of tracker.py directly.
:: ============================================================

:: Get the directory where this bat file lives
SET DIR=%~dp0

:: Step 1: Run tracker.py as a completely independent process
echo [%TIME%] Running tracker.py...
"%DIR%venv\Scripts\python.exe" "%DIR%tracker.py" %*
IF ERRORLEVEL 1 (
    echo [%TIME%] tracker.py failed. Exiting.
    exit /b 1
)
echo [%TIME%] tracker.py completed.

:: Step 2: Check if a new month sheet was created
SET FLAG=%DIR%new_sheet_created.flag
IF NOT EXIST "%FLAG%" (
    echo [%TIME%] No new sheet created. Skipping fix_chart_color.py.
    exit /b 0
)

:: Read month name from flag file
SET /p MONTH_NAME=<"%FLAG%"
echo [%TIME%] New sheet detected: %MONTH_NAME%
echo [%TIME%] Running fix_chart_color.py...

:: Step 3: Run fix_chart_color.py as a completely independent process
"%DIR%venv\Scripts\python.exe" "%DIR%fix_chart_color.py" "%MONTH_NAME%"
IF ERRORLEVEL 1 (
    echo [%TIME%] fix_chart_color.py failed.
) ELSE (
    echo [%TIME%] fix_chart_color.py completed successfully.
)

:: Step 4: Delete the flag file so it doesn't trigger again tomorrow
DEL "%FLAG%"
echo [%TIME%] Flag cleared.
exit /b 0
