# PEARL News Platform v5.0 — Direct GitHub to Google Drive

## Purpose

Version 5.0 removes the Windows Task Scheduler from the production data flow.
GitHub Actions collects and reports the data, then uploads files directly to
Google Drive using rclone OAuth.

## Production flow

```text
GitHub Actions schedule
  -> Python daily/weekly/monthly process
  -> CSV/XLSX/DOCX/log/master outputs
  -> rclone upload
  -> Google Drive/PEARL-News-Archive
```

The PC may be switched off after deployment. Windows Task Scheduler is not
required.

## Google Drive structure

```text
PEARL-News-Archive/
  daily/YYYY/MM/DD/
  weekly/YYYY/W##/
  monthly/YYYY/MM/
  qa/YYYY/MM/DD/
  raw_archive/YYYY/MM/DD/
  logs/YYYY/MM/
  master/
  master_backups/YYYY/MM/
  manifests/daily|weekly|monthly/YYYY/MM/
```

Folder selection comes from the report date in each filename, not from upload
time. Re-running a workflow writes to the same deterministic destination. Rclone
skips identical files and replaces changed canonical files without creating
local timestamp duplicates.

## Fast CMD setup

1. Extract the package over your repository after making a backup.
2. Open Command Prompt.
3. Run:

```cmd
cd /d D:\001_GitHub\PEARL-Data-Platform
setup_v5_google_drive.cmd
```

The script checks/installs rclone, verifies GitHub CLI authentication, starts the
Google browser authorization if needed, tests Google Drive, creates the GitHub
secret `RCLONE_CONFIG`, compiles Python, and runs tests.

The only non-CMD step is approving Google OAuth in the browser when rclone opens
it. Do not share or commit `rclone.conf`.

## Deploy through CMD

```cmd
cd /d D:\001_GitHub\PEARL-Data-Platform
git switch -c version-5.0-google-drive
git add -A
git commit -m "Release v5.0 - direct Google Drive automation"
git push -u origin version-5.0-google-drive
```

Test daily:

```cmd
gh workflow run daily_news.yml --repo Mardy168/PEARL-Data-Platform --ref version-5.0-google-drive
gh run watch --repo Mardy168/PEARL-Data-Platform
```

Test weekly and monthly:

```cmd
gh workflow run weekly_report.yml --repo Mardy168/PEARL-Data-Platform --ref version-5.0-google-drive
gh workflow run monthly_report.yml --repo Mardy168/PEARL-Data-Platform --ref version-5.0-google-drive -f report_month=2026-06
```

## Production activation

Scheduled workflows run from the repository default branch. After all three
manual tests succeed, merge `version-5.0-google-drive` into the default branch.
Keep GitHub artifact fallback for 14–60 days during initial operation.

Disable the old Windows task only after successful Google Drive verification:

```cmd
schtasks /Change /TN "PEARL Daily Artifact Sync v4.2" /DISABLE
```

Do not delete it immediately; keep it disabled for one week as rollback.

## Schedule (Cambodia time)

- Daily: approximately 09:05 every day
- Weekly: Friday approximately 11:05
- Monthly: first day of month approximately 09:05, reporting the previous month

GitHub scheduled workflows can occasionally start a few minutes late.
