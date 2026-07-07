# PEARL Data Platform - Phase 2

This phase adds a stronger PEARL news and market-intelligence foundation.

## What it does

- Collects daily crop intelligence for Mango, Cashew, Rice and Vegetables.
- Searches Cambodia and global trends using Google News RSS and GDELT.
- Adds curated RSS sources where available.
- Classifies each record by crop, topic and Cambodia/global source group.
- Creates CSV and Excel outputs.
- Uploads outputs to Google Drive.
- Generates a weekly Word report by downloading recent daily CSVs from Google Drive.

## Required GitHub Secrets

- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`

## Manual run

GitHub > Actions > PEARL Daily News Collection > Run workflow

GitHub > Actions > PEARL Weekly Report > Run workflow

## Schedule

- Daily collection: 07:00 Cambodia time
- Weekly report: Friday 16:00 Cambodia time

## Main folders

```text
config/keywords.json
config/sources.json
src/collectors/news.py
src/drive/upload.py
src/reports/weekly.py
src/utils/classify.py
src/main.py
```

## Outputs in Google Drive

```text
PEARL_daily_news_YYYY-MM-DD.csv
PEARL_daily_news_YYYY-MM-DD.xlsx
PEARL_weekly_commonality_report_YYYY-MM-DD.docx
```
