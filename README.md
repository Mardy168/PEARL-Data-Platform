# PEARL News Collection Platform v2.2

**Release focus:** safe master repository, historical recovery, and consistent daily/weekly/monthly reporting.

## Reporting rules

- Daily: exact rolling 24 hours; only articles not already present in the master.
- Weekly: exact rolling seven days from the authoritative master.
- Monthly: previous completed calendar month by default; manual `YYYY-MM` supported.
- Deduplication: remove identical canonical URL and identical publisher + normalized title; retain similar stories from different publishers.

## Master safety controls

1. Missing or unreadable master stops the workflow.
2. Multiple production files with the same name stop the workflow.
3. Every daily update creates a timestamped Drive backup.
4. Updates target the exact Drive file ID.
5. A proposed master cannot contain fewer records than the loaded master.
6. No-change daily runs do not rewrite the master.
7. QA logs record master before/after counts, Drive file ID, and backup filename.

## Optional secret

`GOOGLE_MASTER_FILE_ID` is recommended. When present, the workflows update exactly that Drive file. Without it, v2.2 requires exactly one `PEARL_master_news.csv` in the configured folder.

## Historical recovery

1. Upload your pre-v2.1 backup to the configured Drive folder as `PEARL_master_news_RECOVERY_INPUT.csv`.
2. Run **PEARL Recover Master (Manual Only)** from the v2.2 branch.
3. The workflow backs up production, merges and deduplicates both files, generates a recovery QA workbook, and only then updates the exact production master.

Do not delete recovery inputs or backups until all daily, weekly, and monthly tests pass.
