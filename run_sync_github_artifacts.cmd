@echo off
setlocal
cd /d "%~dp0"
if "%PEARL_ARCHIVE_ROOT%"=="" set "PEARL_ARCHIVE_ROOT=D:\001_GitHub\PEARL-News-Archive"
python tools\sync_github_artifacts.py --repo Mardy168/PEARL-Data-Platform --days 7
if errorlevel 1 exit /b 1
endlocal
