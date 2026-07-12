@echo off
setlocal EnableExtensions

cd /d "%~dp0"

if not defined PEARL_ARCHIVE_ROOT (
    set "PEARL_ARCHIVE_ROOT=D:\001_GitHub\PEARL-News-Archive"
)

if not defined PEARL_GITHUB_REPOSITORY (
    set "PEARL_GITHUB_REPOSITORY=Mardy168/PEARL-Data-Platform"
)

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found.
    exit /b 1
)

where gh >nul 2>&1
if errorlevel 1 (
    echo ERROR: GitHub CLI was not found.
    echo Install it with:
    echo winget install --id GitHub.cli
    exit /b 1
)

gh auth status >nul 2>&1
if errorlevel 1 (
    echo ERROR: GitHub CLI is not authenticated.
    echo Run:
    echo gh auth login
    exit /b 1
)

python "tools\sync_github_artifacts.py" ^
  --repo "%PEARL_GITHUB_REPOSITORY%" ^
  --archive-root "%PEARL_ARCHIVE_ROOT%" ^
  --limit 100 ^
  --latest-per-category 10

set "SYNC_EXIT_CODE=%ERRORLEVEL%"

if not "%SYNC_EXIT_CODE%"=="0" (
    echo.
    echo ERROR: PEARL artifact synchronization failed with exit code %SYNC_EXIT_CODE%.
    exit /b %SYNC_EXIT_CODE%
)

echo.
echo PEARL artifact synchronization completed successfully.
exit /b 0