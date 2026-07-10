# PEARL News Collection Platform v2.2

Release date: 10 July 2026

## Purpose

Version 2.2 protects the authoritative master news repository and restores historical data safely. It retains the consistent reporting windows introduced in Version 2.1.

## Major changes

- Abort when the production master cannot be found or read.
- Abort when duplicate production masters with the same name are found.
- Optional `GOOGLE_MASTER_FILE_ID` secret for exact-file updates.
- Create a timestamped Google Drive backup before each daily master update.
- Prevent the new master from having fewer records than the loaded master.
- Verify the CSV after writing and before uploading.
- Do not rewrite the master when a daily run finds no new articles.
- Add master before/after counts, Drive file ID, and backup name to QA logs.
- Weekly and monthly reports use the same validated production master.
- Add manual historical-recovery workflow and QA workbook.
- Add local master recovery and validation tools.

## New files

- `src/master/manager.py`
- `src/master/__init__.py`
- `tools/recover_master.py`
- `tools/recover_master_from_drive.py`
- `tools/validate_master.py`
- `.github/workflows/recover_master.yml`

## Recovery input name

Upload the historical backup as:

`PEARL_master_news_RECOVERY_INPUT.csv`

Then run the manual workflow **PEARL Recover Master (Manual Only)**.
