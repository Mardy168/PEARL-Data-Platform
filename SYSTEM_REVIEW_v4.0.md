# PEARL News Automation — Version 4.0 System Review

## Scope and evidence reviewed

Reviewed the supplied Version 3 repository: three Python entry points, collector,
date and duplicate utilities, master manager, Excel/Word reporting, Google Drive
client, four GitHub Actions workflows, configuration files and unit tests.

No Google enforcement log was supplied. Therefore, the exact reason Google
disabled an account cannot be proven from repository code alone.

## Existing Version 3 data flow

1. GitHub Actions runs on a UTC cron.
2. The Python job authenticates as a Google service account.
3. It downloads the production master CSV from Drive.
4. Before collection, it copies the master into `Master_Backups`.
5. It requests 16 Google News RSS searches and five curated RSS feeds.
6. It parses publication timestamps, filters a rolling period, deduplicates rows,
   creates summaries and updates the master.
7. It uploads CSV, XLSX, DOCX, QA, log and raw-archive files to Drive.
8. Weekly and monthly jobs independently download the Drive master and filter it.

## Root causes found

### Authentication and storage

* Version 3 uses a service account against Drive. A service account has no
  personal storage quota and cannot own files. It must use a Workspace Shared
  Drive or act on behalf of a human through OAuth.
* The supplied workflow passes only `GOOGLE_SERVICE_ACCOUNT_JSON`; the OAuth
  client ID, client secret and refresh token are not used by the supplied code.
* Every daily run creates a Drive backup before validation and even when no new
  article exists. Repeated manual tests therefore create unnecessary copies.
* Every run also uploads a raw archive and five report files. This is inefficient,
  though the repository alone does not prove it caused an account suspension.
* Creating/replacing OAuth clients and refresh tokens repeatedly is operationally
  fragile. The exact Google account enforcement decision remains unknown.

### Daily/weekly inconsistency

* The daily Excel used every unique article in the 24-hour window, including
  articles already present in the master. Only `new_articles` were added to the
  master. Weekly/monthly read the master, so daily and weekly could legitimately
  show different counts for the same article set.
* Version 4 makes the daily report contain only articles that are new to the same
  normalized master used by weekly and monthly reports.

### Timezone and boundaries

* The UTC cron values were correct for Cambodia, but the daily window ended at
  the actual delayed run time. Delayed GitHub execution could move the window and
  create overlaps or gaps.
* Version 4 uses the latest completed 09:00 Cambodia boundary and a half-open
  interval `[start, end)`. Weekly and monthly use the same half-open rule.
* Invalid timestamps are excluded and counted in QA.
* Assumption: feed timestamps without an explicit timezone are interpreted as
  UTC. The configured feeds normally return timestamps with offsets.

### Pagination and row limits

* RSS has no standard page-by-page history endpoint. The collector receives the
  current feed only and slices to 100 entries. It cannot guarantee completeness
  when a feed returns 100 or more rows.
* Version 4 records `row_limit` and `possibly_truncated` in Source Health.
* Excel supports 1,048,576 total worksheet rows. Version 4 refuses more than
  1,048,575 data rows plus the header.
* The normalized master remains CSV and is not subject to the Excel row limit.

### Deduplication

* Version 3 sorted mixed strings and Pandas timestamps directly, causing the
  observed `TypeError`.
* Version 4 converts all candidate date columns to UTC before stable sorting.
* It removes tracking parameters, retains the same event from different
  publishers, deduplicates exact canonical URLs and then same-site normalized
  titles.

## Version 4 storage architecture

### Default GitHub mode

* `data/master/PEARL_master_news.csv` is the durable normalized master and is the
  only generated data file committed to the repository.
* Daily, weekly and monthly files are uploaded as GitHub Actions artifacts.
* Daily outputs retain for 30 days, weekly for 60 days and monthly for 90 days.
* Weekly and monthly jobs read the exact same committed master CSV.

### Local PC / Google Drive for desktop mode

Run the same scripts on Windows and set `PEARL_DATA_ROOT` to a local folder or a
Google Drive for desktop synced folder. Google Drive for desktop performs the
sync; Python and GitHub do not use Google OAuth or the Drive API.

Example:

```cmd
set PEARL_DATA_ROOT=G:\My Drive\PEARL_Commodity_Data
run_local_daily.cmd
```

This requires the PC to be on when Windows Task Scheduler starts the job.

### Optional cloud recommendation

GitHub artifacts are the simplest free temporary cloud output store. They are
not permanent archives. For long-term organizational storage, use an approved
Workspace Shared Drive. A service account is appropriate only when writing into
that Shared Drive. Do not reconnect a newly created consumer Gmail account to
unattended automation until the account and OAuth application are stable and
approved for that use.

## Files replaced in Version 4

* `pearl_daily_collector.py`
* `pearl_weekly_report.py`
* `pearl_monthly_report.py`
* `src/collectors/collector.py`
* `src/utils/dates.py`
* `src/utils/duplicate.py`
* `src/master/manager.py`
* `src/utils/excel.py`
* `src/drive/drive.py` (disabled compatibility module)
* `.github/workflows/daily_news.yml`
* `.github/workflows/weekly_report.yml`
* `.github/workflows/monthly_report.yml`
* `.gitignore`
* `requirements.txt`
* `tests/test_core.py`

Removed:

* `.github/workflows/recover_master.yml`
* `tools/recover_master_from_drive.py`

Added:

* `run_local_daily.cmd`
* `run_local_weekly.cmd`
* `run_local_monthly.cmd`
* `SYSTEM_REVIEW_v4.0.md`

## Test commands

```cmd
cd /d D:\001_GitHub\PEARL-Data-Platform
python -m pip install -r requirements.txt
python -m compileall -q .
python -m unittest discover -s tests -v
```

Expected unit-test result:

```text
Ran 7 tests
OK
```

Local daily test:

```cmd
set PEARL_DATA_ROOT=D:\001_GitHub\PEARL_Test_Data
python pearl_daily_collector.py
```

Expected folders:

```text
PEARL_Test_Data\master
PEARL_Test_Data\daily
PEARL_Test_Data\qa
PEARL_Test_Data\logs
PEARL_Test_Data\raw_archive
PEARL_Test_Data\master_backups
```

A live collection test requires outbound network access and responsive RSS
sources. The supplied package passed compilation and all seven deterministic
unit tests; a complete live-feed run was not verified in the review environment.
