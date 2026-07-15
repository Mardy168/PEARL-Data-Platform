# Update from v4.2 to v4.2.1

Replace these complete files:

- `src/utils/dates.py`
- `pearl_daily_collector.py`
- `tools/sync_github_artifacts.py`
- `tests/test_core.py`
- `.github/workflows/daily_news.yml`
- `.github/workflows/weekly_report.yml`
- `.github/workflows/monthly_report.yml`

Do not delete `.git` or the populated `data/master/PEARL_master_news.csv`.

## Local validation

```cmd
cd /d D:\001_GitHub\PEARL-Data-Platform
python -m compileall -q .
python -m unittest discover -s tests -v
python tools\sync_github_artifacts.py --help
```

Expected: all tests pass and the help contains `--archive-root`, `--limit`, and `--latest-per-category`.

## Manual sync test

```cmd
run_sync_github_artifacts.cmd
```

Expected ending:

```text
Errors                : 0
PEARL artifact synchronization completed successfully.
```

## Optional one-time repair of existing archive folders

Preview only:

```cmd
python tools\repair_archive_layout.py --archive-root "D:\001_GitHub\PEARL-News-Archive"
```

Apply the moves after reviewing the preview:

```cmd
python tools\repair_archive_layout.py --archive-root "D:\001_GitHub\PEARL-News-Archive" --apply
```
