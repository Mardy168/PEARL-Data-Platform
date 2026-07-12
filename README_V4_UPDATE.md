# Update to PEARL Version 4.0

1. Make a backup of the current repository folder.
2. Disable the Version 3 GitHub workflows.
3. Copy the Version 4 files over the repository, preserving `.git`.
4. Run the compilation and unit tests in `SYSTEM_REVIEW_v4.0.md`.
5. Commit and push Version 4 to a new branch.
6. Open a pull request and merge Version 4 into the repository default branch.
   Scheduled GitHub Actions execute from the default branch.
7. Run the daily workflow manually once.
8. Confirm the workflow artifact contains daily, QA, log, raw archive and master.
9. Confirm the workflow created or updated only
   `data/master/PEARL_master_news.csv` in the repository.
10. Run weekly and monthly manually and confirm both read that same master.

No Google secrets are required in Version 4 GitHub Actions. Existing Google
secrets can remain temporarily, but the Version 4 workflows do not reference
them. Remove them after Version 4 is verified and after retaining any credentials
needed elsewhere.
