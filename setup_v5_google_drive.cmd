@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "REPO=Mardy168/PEARL-Data-Platform"
set "REMOTE=pearl-drive"
set "CONFIG=%APPDATA%\rclone\rclone.conf"

echo ============================================================
echo PEARL News Platform v5.0 - Google Drive Setup
echo ============================================================
echo.

where gh >nul 2>&1 || (
  echo ERROR: GitHub CLI is not installed or not on PATH.
  echo Install it with: winget install GitHub.cli
  exit /b 1
)

where rclone >nul 2>&1 || (
  echo rclone is not installed. Installing with winget...
  winget install --id Rclone.Rclone -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 exit /b 1
  echo Close and reopen Command Prompt, then run this file again.
  exit /b 0
)

gh auth status >nul 2>&1 || (
  echo GitHub CLI is not signed in.
  gh auth login
  if errorlevel 1 exit /b 1
)

if not exist "%CONFIG%" (
  echo.
  echo Rclone Google Drive authorization will start now.
  echo Create a remote named exactly: %REMOTE%
  echo Select Google Drive and sign in with pearl.agriculture.data@gmail.com.
  echo.
  rclone config
  if errorlevel 1 exit /b 1
)

rclone listremotes | findstr /x /c:"%REMOTE%:" >nul || (
  echo ERROR: Remote %REMOTE% was not found in %CONFIG%.
  echo Run: rclone config
  echo Create or rename the Google Drive remote to %REMOTE%.
  exit /b 1
)

echo.
echo Testing Google Drive connection...
rclone mkdir "%REMOTE%:PEARL-News-Archive/test"
if errorlevel 1 exit /b 1
> "%TEMP%\pearl_v5_test.txt" echo PEARL v5 Google Drive test
rclone copyto "%TEMP%\pearl_v5_test.txt" "%REMOTE%:PEARL-News-Archive/test/pearl_v5_test.txt" -v
if errorlevel 1 exit /b 1

echo.
echo Saving rclone OAuth configuration as GitHub Secret RCLONE_CONFIG...
gh secret set RCLONE_CONFIG --repo "%REPO%" < "%CONFIG%"
if errorlevel 1 exit /b 1

echo.
echo Validating source code...
python -m compileall -q .
if errorlevel 1 exit /b 1
python -m unittest discover -s tests -v
if errorlevel 1 exit /b 1

echo.
echo ============================================================
echo SETUP COMPLETED SUCCESSFULLY
echo ============================================================
echo Next commands:
echo   git switch -c version-5.0-google-drive
echo   git add -A
echo   git commit -m "Release v5.0 - direct Google Drive automation"
echo   git push -u origin version-5.0-google-drive
echo.
echo Then test:
echo   gh workflow run daily_news.yml --repo %REPO% --ref version-5.0-google-drive
echo   gh run watch --repo %REPO%
endlocal
