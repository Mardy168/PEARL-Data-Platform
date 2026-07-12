# PEARL News Platform Version 4.1

Version 4.1 retains the Version 4 normalized-master architecture and adds a permanent Windows archive.

## Storage design
- GitHub Actions: collects and generates artifacts; commits only `data/master/PEARL_master_news.csv`.
- GitHub artifacts: temporary delivery and recovery copies.
- Windows archive: `D:\001_GitHub\PEARL-News-Archive` for permanent daily, weekly, monthly, QA, raw, log and backup files.

A GitHub-hosted runner cannot directly write to a local D: drive. Permanent local storage is populated by either:
1. running `run_local_*.cmd` on the PC, or
2. scheduling `run_sync_github_artifacts.cmd` after the GitHub workflow finishes.

## Added
- `src/archive/manager.py`
- collision-safe historical copies
- date-organized archive folders
- monthly ZIP archive
- `tools/sync_github_artifacts.py`
- `run_sync_github_artifacts.cmd`
- archive unit tests
