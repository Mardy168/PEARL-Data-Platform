# PEARL News Collection Platform v3.0

## Critical defects fixed from v2.2

- Rebuilt `pearl_daily_collector.py`, which had been accidentally replaced by Drive-authentication code and therefore could not collect news.
- Corrected invalid YAML indentation in Weekly and Monthly workflows.
- Migrated the Recovery workflow from disabled-account OAuth secrets to service-account authentication.
- Added correct service-account imports and JSON parsing.
- Routed outputs to the intended Drive subfolders.
- Fixed Daily/Weekly inconsistency: Daily now reports all unique articles in the rolling 24-hour window, while only new articles are appended to the master.
- Added raw snapshots, QA source-health reporting, stable master backups and exact master-file updates.
- Corrected Excel width handling and added a `Master Status` column.
- Added syntax validation and automated core tests.

## Reporting schedule

- Daily: 09:00 Cambodia time.
- Weekly: Friday 11:00 Cambodia time.
- Monthly: first day of month at 09:00 Cambodia time, reporting the previous completed month.
