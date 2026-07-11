# PEARL News Collection Platform v3.0

Production-oriented daily, weekly and monthly monitoring for rice, mango, cashew and vegetables.

## Authoritative data model

- **Master CSV**: the only authoritative article repository.
- **Daily report**: every unique article published during the rolling 24-hour window, including articles already in the master. The `Master Status` column shows `NEW` or `EXISTING`.
- **Weekly report**: rolling seven days, generated only from the master.
- **Monthly report**: previous completed calendar month by default, generated only from the master.
- **Deduplication**: canonical URL, then publisher-domain plus normalized title. Similar reporting by different publishers is retained.

## Required Google Drive structure

```text
PEARL_Commodity_Data_Collection
├── Daily
├── Logs
├── Master
├── Master_Backups
├── Monthly
├── QA
├── Raw_Archive
└── Weekly
```

The code resolves these subfolders by exact name. Duplicate or missing folder names stop the workflow.

## Required GitHub repository secrets

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_DRIVE_FOLDER_ID` — ID of the main folder above
- `GOOGLE_MASTER_FILE_ID` — ID of the real CSV file in `Master`

The master must be an actual `.csv`, not a native Google Sheet.

## Safety controls

1. Missing, empty or unreadable master stops all workflows.
2. Daily creates a timestamped master backup before collection.
3. Master updates target the exact configured file ID.
4. A proposed master cannot contain fewer unique records than the loaded master.
5. Daily reports remain reproducible on reruns because existing-in-master articles remain in the 24-hour report.
6. Weekly and monthly are always derived from the same authoritative master.
7. QA workbooks record source health, publication-date validity, master counts and window counts.
8. Raw collection snapshots are archived for diagnosis.

## Local validation

```bash
python -m pip install -r requirements.txt
python -m compileall -q .
python -m unittest discover -s tests
```

## Important service-account note

A service account must have Editor access to the main Drive folder. On some consumer My Drive setups, Google may reject creation of new files because service accounts have no personal storage quota. In that case, use a Google Workspace Shared Drive or switch the authentication layer to an authorized user OAuth account while keeping the same data-engineering logic.
