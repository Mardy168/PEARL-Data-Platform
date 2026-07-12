@echo off
setlocal
cd /d "%~dp0"
if "%PEARL_DATA_ROOT%"=="" set "PEARL_DATA_ROOT=%~dp0data"
if "%PEARL_ARCHIVE_ROOT%"=="" set "PEARL_ARCHIVE_ROOT=D:\001_GitHub\PEARL-News-Archive"
python pearl_daily_collector.py
if errorlevel 1 (
  echo PEARL daily run failed.
  exit /b 1
)
echo PEARL daily run completed and archived to %PEARL_ARCHIVE_ROOT%.
endlocal
