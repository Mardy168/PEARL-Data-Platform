"""Generate corrected historical reports from the cleaned master without overwriting old files.
Set REPORT_DATE=YYYY-MM-DD for a daily corrected report.
Set REPORT_MONTH=YYYY-MM for a monthly corrected report.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from src.utils.dates import CAMBODIA_TZ, add_published_columns, remove_timezone_columns
from src.utils.duplicate import deduplicate_articles
from src.utils.excel import write_excel

MASTER = Path("data/master/PEARL_master_news.csv")
OUT = Path("data/corrected")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = add_published_columns(pd.read_csv(MASTER))
    report_date = os.getenv("REPORT_DATE", "").strip()
    if report_date:
        end = datetime.strptime(report_date + " 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=CAMBODIA_TZ)
        start = end - timedelta(hours=24)
        result = deduplicate_articles(df[(df.published_dt_kh >= start) & (df.published_dt_kh <= end)])
        write_excel(remove_timezone_columns(result), str(OUT / f"PEARL_daily_news_{report_date}_CORRECTED.xlsx"))
        return
    raise ValueError("Set REPORT_DATE=YYYY-MM-DD")

if __name__ == "__main__":
    main()
