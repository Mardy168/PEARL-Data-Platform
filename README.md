# PEARL Data Platform - Phase 1

This phase creates a working cloud automation that collects daily Cambodia/global crop news for PEARL commonality crops and uploads CSV/XLSX outputs to Google Drive.

## Required GitHub Secrets

- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`

## Manual Run

GitHub > Actions > PEARL Daily News Collection > Run workflow

## Schedule

- Daily collection: 07:00 Cambodia time
- Weekly report: Friday 16:00 Cambodia time

## Crops

- Mango
- Cashew
- Rice
- Vegetables
