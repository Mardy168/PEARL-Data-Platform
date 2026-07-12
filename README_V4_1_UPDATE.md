# Version 4.1 update checklist

1. Back up the Version 4 repository.
2. Copy this package over the repository while retaining `.git` and the current populated `data/master/PEARL_master_news.csv`.
3. Set `PEARL_ARCHIVE_ROOT=D:\001_GitHub\PEARL-News-Archive`.
4. Install requirements and run tests.
5. Create and push branch `version-4.1`.
6. Test daily, weekly and monthly workflows.
7. Install GitHub CLI and schedule `run_sync_github_artifacts.cmd` on the Windows PC for permanent automatic archive synchronization.
