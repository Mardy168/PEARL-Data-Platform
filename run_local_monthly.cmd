@echo off
setlocal
cd /d %~dp0
if "%PEARL_DATA_ROOT%"=="" set "PEARL_DATA_ROOT=%~dp0data"
python pearl_monthly_report.py
if errorlevel 1 exit /b 1
endlocal
