@echo off
setlocal
cd /d "%~dp0"
set "RCLONE_REMOTE_NAME=pearl-drive"
set "GOOGLE_DRIVE_ROOT=PEARL-News-Archive"
python tools\upload_google_drive.py --workflow all --dry-run
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo ERROR: Dry-run failed with exit code %RC%.
exit /b %RC%
