Replace only:
- run_sync_github_artifacts.cmd
- tools/sync_github_artifacts.py

Test:
cd /d D:\001_GitHub\PEARL-Data-Platform
run_sync_github_artifacts.cmd

Commit:
git add run_sync_github_artifacts.cmd tools\sync_github_artifacts.py
git commit -m "Release Version 4.2 - filtered artifact synchronization"
git push -u origin version-4.2
