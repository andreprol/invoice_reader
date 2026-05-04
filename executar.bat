@echo off
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
    py app.py
) else (
    python app.py
)
