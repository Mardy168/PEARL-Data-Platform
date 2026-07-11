# Senior Engineering Review — PEARL v2.2 to v3.0

## Overall assessment

Version 2.2 was not production-ready. The master-protection design was useful, but several critical integration defects prevented reliable execution and caused the Daily, Weekly and Monthly outputs to diverge.

## Critical findings

1. **Daily collector destroyed**: `pearl_daily_collector.py` contained only Google Drive authentication code. It never collected, filtered, reported or updated the master.
2. **Invalid GitHub Actions YAML**: Weekly and Monthly `env` blocks were incorrectly indented, causing workflow-file failures.
3. **Mixed authentication models**: Daily/Weekly/Monthly were partly migrated to a service account while Recovery still used the disabled user's OAuth secrets.
4. **Daily reproducibility defect**: prior logic reported only articles not already in the master, so rerunning the same 24-hour period produced “no news” even when valid current articles existed.
5. **Folder architecture unused**: all files were uploaded to one root folder despite Daily, Weekly, Monthly, QA, Logs, Master_Backups and Raw_Archive folders being created.
6. **No raw evidence archive**: it was impossible to diagnose whether a missing article was not returned, had an invalid date, was outside the window, or was removed as a duplicate.
7. **Weak operational validation**: workflows did not compile the Python package before execution and had no automated core tests.
8. **Excel formatting defect**: column-width code was unsafe beyond column Z and could assign widths incorrectly.
9. **Stale/broken legacy module**: `src/main.py` referenced modules that did not exist and was removed.
10. **Google service-account risk**: consumer My Drive can reject creation of new service-account-owned files. The code now reports this clearly; Workspace Shared Drive is the durable production target.

## v3.0 design

- One authoritative master CSV.
- Daily output contains all unique articles within the current rolling 24 hours.
- `Master Status` identifies `NEW` versus `EXISTING` articles.
- Only `NEW` articles are appended to the master.
- Weekly and Monthly reports are generated only from the authoritative master.
- Every Daily run creates a timestamped pre-update backup.
- Raw RSS results are archived for QA and incident review.
- Drive subfolders are resolved by exact name; missing or duplicate folders stop the workflow.
- All workflows use one authentication model and the same three GitHub secrets.
- Syntax checks and core tests are included.

## Validation completed

- All Python files compiled successfully with Python 3.11.
- All four GitHub Actions YAML files parsed successfully.
- Four automated core tests passed: timezone conversion, month boundaries, duplicate handling and exclusion of existing master records.
- No references remain to the old OAuth secrets or broken legacy imports.
