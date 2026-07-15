# Release Notes — Version 5.0

- Removed Windows Task Scheduler from the production architecture.
- Added direct GitHub Actions to Google Drive upload using rclone OAuth.
- Added deterministic report-date folder routing.
- Added daily, weekly, monthly, QA, raw, log, master and backup routing.
- Added SHA-256 run manifest uploaded for every workflow.
- Added retries and checksum verification.
- Kept GitHub artifacts temporarily as rollback protection.
- Added one-command Windows setup helper.
- Added unit tests for Google Drive destination paths.
