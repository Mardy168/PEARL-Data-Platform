# PEARL News Collection Platform v2.1

Production baseline for automated rice, mango, cashew and vegetable news monitoring.

## Reporting rules
- Daily: exact previous 24 hours, only records not already in the master.
- Weekly: exact rolling seven days from the master.
- Monthly: previous completed calendar month by default.
- Same story from different publishers is retained.
- Same canonical URL or same publisher + normalized title is removed.

## Outputs
Daily CSV, Excel, one-page Word summary, log, QA workbook and updated master CSV. Weekly and monthly produce Excel, Word and logs.

## Excel date
`Published Date` is Cambodia time formatted as `YYYY-MM-DD HH:MM:SS`.

## Required GitHub secrets
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GOOGLE_DRIVE_FOLDER_ID`.

## One-time tools
- `python tools/clean_master.py`
- `python tools/regenerate_corrected_reports.py`
