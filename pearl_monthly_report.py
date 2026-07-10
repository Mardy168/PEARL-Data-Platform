from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
import pandas as pd

from src.drive.drive import download_file_by_name, upload_file
from src.reports.common import configure_document, add_news_section
from src.utils.dates import CAMBODIA_TZ, add_published_columns, now_cambodia, previous_month_window, remove_timezone_columns
from src.utils.duplicate import deduplicate_articles
from src.utils.excel import write_excel

OUTPUT_MONTHLY = Path("data/monthly")
OUTPUT_LOGS = Path("data/logs")
MASTER_FILE = Path("data/master/PEARL_master_news.csv")
MASTER_FILENAME = MASTER_FILE.name


def resolve_window(now):
    explicit = os.getenv("REPORT_MONTH", "").strip()
    if explicit:
        start = datetime.strptime(explicit + "-01", "%Y-%m-%d").replace(tzinfo=CAMBODIA_TZ)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end, explicit
    return previous_month_window(now)


def main() -> None:
    OUTPUT_MONTHLY.mkdir(parents=True, exist_ok=True)
    OUTPUT_LOGS.mkdir(parents=True, exist_ok=True)
    MASTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    download_file_by_name(MASTER_FILENAME, str(MASTER_FILE))
    if not MASTER_FILE.exists():
        raise FileNotFoundError("Master file is missing. Run daily collector first.")

    now = now_cambodia()
    start, end, report_month = resolve_window(now)
    df = add_published_columns(pd.read_csv(MASTER_FILE))
    monthly = df[df["published_dt_kh"].notna() &
                 (df["published_dt_kh"] >= start) &
                 (df["published_dt_kh"] < end)].copy()
    monthly = deduplicate_articles(monthly)
    monthly = monthly[monthly.get("status", "ARTICLE").astype(str).eq("ARTICLE")] if "status" in monthly.columns else monthly
    monthly = monthly.sort_values("published_dt_kh", ascending=False)

    xlsx = OUTPUT_MONTHLY / f"PEARL_monthly_news_{report_month}.xlsx"
    docx = OUTPUT_MONTHLY / f"PEARL_monthly_summary_{report_month}.docx"
    log = OUTPUT_LOGS / f"PEARL_monthly_log_{report_month}.txt"
    write_excel(remove_timezone_columns(monthly), str(xlsx))

    doc = configure_document("PEARL Monthly Agriculture News Summary",
                             f"Completed month: {report_month}")
    cambodia = monthly[monthly["country"].astype(str).str.lower().eq("cambodia")]
    global_news = monthly[~monthly["country"].astype(str).str.lower().eq("cambodia")]
    add_news_section(doc, "Page 1: Cambodia Monthly News", cambodia, 15)
    doc.add_page_break(); add_news_section(doc, "Page 2: Global Monthly News", global_news, 15)
    doc.add_page_break(); doc.add_heading("Page 3: Statistics", 1)
    doc.add_paragraph(f"Total unique articles: {len(monthly)}")
    for label, col in (("Country", "country"), ("Crop", "crop"), ("Topic", "topic")):
        doc.add_heading(f"By {label}", 2)
        for value, count in monthly[col].fillna("Unknown").value_counts().items():
            doc.add_paragraph(f"- {value}: {count}")
    doc.save(docx)

    with open(log, "w", encoding="utf-8") as f:
        f.write(f"Monthly period: {start} to {end}\nUnique articles: {len(monthly)}\n")
    for path in (xlsx, docx, log): upload_file(str(path))
    print("Monthly report completed successfully.")


if __name__ == "__main__":
    main()
