# PEARL News Platform v4.2.1

## Purpose

This maintenance release fixes report-date folder placement without changing the working collection, master, deduplication, Excel, Word, or GitHub Artifact architecture.

## Root causes fixed

1. The daily collector used the execution calendar date for filenames instead of the completed 09:00 Cambodia reporting boundary date.
2. The Windows artifact synchronizer used the GitHub workflow creation time to choose archive folders.
3. A report generated for one date but downloaded on the following date could therefore be placed in the wrong folder.

## Correct behavior

- Daily report date is the Cambodia date of the completed 09:00 boundary.
- Daily, QA, raw archive, and log destinations are inferred from each file's `YYYY-MM-DD` report date.
- Monthly destinations are inferred from the `YYYY-MM` report month in filenames.
- Weekly destinations use a week token when present, otherwise the report-date filename.
- GitHub run time is used only when a filename contains no valid report date.

## Expected daily archive

```text
D:\001_GitHub\PEARL-News-Archive\daily\2026\07\14\
    PEARL_daily_news_2026-07-14.csv
    PEARL_daily_news_2026-07-14.xlsx
    PEARL_daily_summary_2026-07-14.docx
```
