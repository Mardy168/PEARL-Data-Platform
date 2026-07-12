# PEARL News Platform Version 4.1 — Installation and Configuration

## Important architecture fact

GitHub Actions runs on a remote GitHub computer. It cannot directly write to:

`D:\001_GitHub\PEARL-News-Archive`

Version 4.1 therefore uses two automatic layers:

1. GitHub Actions collects news, updates the normalized master and uploads artifacts.
2. Windows Task Scheduler runs `run_sync_github_artifacts.cmd` on your PC to download those artifacts into the permanent local archive.

Local executions using `run_local_daily.cmd`, `run_local_weekly.cmd`, or `run_local_monthly.cmd` archive outputs immediately.

## A. Back up Version 4

Copy:

`D:\001_GitHub\PEARL-Data-Platform`

To:

`D:\001_GitHub\PEARL-Data-Platform-v4-backup`

Keep the populated file:

`data\master\PEARL_master_news.csv`

## B. Replace the project files

1. Extract `PEARL-Data-Platform-v4.1.zip`.
2. Open the extracted folder.
3. Copy all contents.
4. Paste into `D:\001_GitHub\PEARL-Data-Platform`.
5. Choose **Replace the files in the destination**.
6. Do not delete the hidden `.git` folder.
7. If the copied package contains an empty `data\master`, restore your populated `PEARL_master_news.csv` from the Version 4 repository or backup.

## C. Configure the archive root

Open Command Prompt and run:

```cmd
setx PEARL_ARCHIVE_ROOT "D:\001_GitHub\PEARL-News-Archive"
```

Close and reopen Command Prompt. Verify:

```cmd
echo %PEARL_ARCHIVE_ROOT%
```

Expected:

`D:\001_GitHub\PEARL-News-Archive`

The scripts create all subfolders automatically.

## D. Install and test

```cmd
cd /d D:\001_GitHub\PEARL-Data-Platform
python -m pip install -r requirements.txt
python -m compileall -q .
python -m unittest discover -s tests -v
```

Expected final lines:

```text
Ran 8 tests
OK
```

## E. Test local archiving

```cmd
run_local_daily.cmd
```

Expected:

- the daily collector completes;
- files remain under repository `data`;
- permanent copies appear under:
  `D:\001_GitHub\PEARL-News-Archive\daily\YYYY\MM\DD`;
- the current master appears under:
  `D:\001_GitHub\PEARL-News-Archive\master`.

Then test:

```cmd
run_local_weekly.cmd
run_local_monthly.cmd
```

The monthly command reports the previous completed month unless `REPORT_MONTH` is set.

## F. Create and push Version 4.1

```cmd
cd /d D:\001_GitHub\PEARL-Data-Platform
git switch -c version-4.1
git add -A
git commit -m "Release Version 4.1 - permanent local archive"
git push -u origin version-4.1
```

Run the daily, weekly and monthly workflows manually on `version-4.1` before merging.

## G. Install GitHub CLI for automatic local downloads

Open Windows Terminal as a normal user and run:

```cmd
winget install --id GitHub.cli
```

Close and reopen Command Prompt. Verify:

```cmd
gh --version
```

Authenticate:

```cmd
gh auth login
```

Choose:

- GitHub.com
- HTTPS
- Login with a web browser

Verify:

```cmd
gh auth status
```

## H. Test artifact synchronization

```cmd
cd /d D:\001_GitHub\PEARL-Data-Platform
run_sync_github_artifacts.cmd
```

Expected:

`Artifact synchronization completed. X files copied to D:\001_GitHub\PEARL-News-Archive.`

The first run downloads recent successful Version 4.1 artifacts. Later runs skip workflow runs recorded in:

`D:\001_GitHub\PEARL-News-Archive\sync_state\downloaded_runs.json`

## I. Configure Windows Task Scheduler

1. Open **Task Scheduler**.
2. Select **Create Task**.
3. General tab:
   - Name: `PEARL GitHub Artifact Sync`
   - Select **Run only when user is logged on** for easiest GitHub CLI authentication.
4. Triggers tab:
   - New trigger: Daily at **10:00 AM Cambodia time**.
   - This is one hour after the 09:00 daily GitHub collection.
5. Actions tab:
   - Program/script:
     `C:\Windows\System32\cmd.exe`
   - Add arguments:
     `/c "D:\001_GitHub\PEARL-Data-Platform\run_sync_github_artifacts.cmd"`
   - Start in:
     `D:\001_GitHub\PEARL-Data-Platform`
6. Conditions tab:
   - Clear **Start the task only if the computer is on AC power** if appropriate.
   - Enable **Wake the computer to run this task** if desired.
7. Settings tab:
   - Enable **Run task as soon as possible after a scheduled start is missed**.
   - Stop the task if it runs longer than 30 minutes.
8. Save, right-click the task, and select **Run**.
9. Confirm files appear in the archive.

The PC must be powered on and connected to the internet for local synchronization.

## J. Expected permanent archive

```text
D:\001_GitHub\PEARL-News-Archive
├── daily\YYYY\MM\DD
├── weekly\YYYY\Wnn
├── monthly\YYYY\MM
├── master\PEARL_master_news.csv
├── master_backups\YYYY\MM
├── qa\YYYY\MM\DD
├── raw_archive\YYYY\MM\DD
├── logs\YYYY\MM
├── monthly_zip\YYYY
└── sync_state
```

## K. Production validation

After the next scheduled daily run, check:

- GitHub workflow is green.
- Artifact exists.
- `Master Before Run` is greater than zero.
- `Master After Run` equals old unique records plus new unique records.
- The local scheduled sync downloads the artifact.
- Daily output contains only the completed 09:00-to-09:00 Cambodia window.
- Weekly and monthly outputs read the same committed normalized master.
