from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from src.master.manager import MASTER_FILENAME, normalized_master_for_reporting
from src.reports.common import add_news_section, configure_document
from src.utils.dates import CAMBODIA_TZ, now_cambodia, previous_month_window, remove_timezone_columns
from src.utils.excel import write_excel

DATA_ROOT = Path(os.getenv("PEARL_DATA_ROOT", "data"))
OUTPUT_MONTHLY = DATA_ROOT / "monthly"
OUTPUT_LOGS = DATA_ROOT / "logs"
MASTER_FILE = DATA_ROOT / "master" / MASTER_FILENAME


def resolve_window(now):
    explicit = os.getenv("REPORT_MONTH", "").strip()
    if explicit:
        try:
            start = datetime.strptime(explicit + "-01", "%Y-%m-%d").replace(tzinfo=CAMBODIA_TZ)
        except ValueError as exc:
            raise ValueError("REPORT_MONTH must use YYYY-MM format.") from exc
        end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        return start, end, explicit
    return previous_month_window(now)


def main() -> None:
    OUTPUT_MONTHLY.mkdir(parents=True, exist_ok=True)
    OUTPUT_LOGS.mkdir(parents=True, exist_ok=True)
    now = now_cambodia()
    start, end, report_month = resolve_window(now)
    master = normalized_master_for_reporting(MASTER_FILE)
    monthly = master.loc[
        master["published_dt_kh"].notna()
        & (master["published_dt_kh"] >= start)
        & (master["published_dt_kh"] < end)
    ].sort_values("published_dt_kh", ascending=False).copy()
    xlsx = OUTPUT_MONTHLY / f"PEARL_monthly_news_{report_month}.xlsx"
    docx = OUTPUT_MONTHLY / f"PEARL_monthly_summary_{report_month}.docx"
    log = OUTPUT_LOGS / f"PEARL_monthly_log_{report_month}.txt"
    write_excel(remove_timezone_columns(monthly), str(xlsx))
    doc = configure_document("PEARL Monthly Agriculture News Summary", f"Completed month: {report_month}")
    cambodia = monthly.loc[monthly["country"].astype(str).str.lower().eq("cambodia")]
    global_news = monthly.loc[~monthly["country"].astype(str).str.lower().eq("cambodia")]
    add_news_section(doc, "Page 1: Cambodia Monthly News", cambodia, 15)
    doc.add_page_break()
    add_news_section(doc, "Page 2: Global Monthly News", global_news, 15)
    doc.add_page_break()
    doc.add_heading("Page 3: Statistics", 1)
    doc.add_paragraph(f"Total unique articles: {len(monthly)}")
    for label, column in (("Country", "country"), ("Crop", "crop"), ("Topic", "topic")):
        doc.add_heading(f"By {label}", 2)
        for value, count in monthly[column].fillna("Unknown").value_counts().items():
            doc.add_paragraph(f"- {value}: {count}")
    doc.save(docx)
    with log.open("w", encoding="utf-8") as handle:
        handle.write(f"Master records loaded: {len(master)}\nMonthly period: {start} to {end} (end exclusive)\nUnique articles: {len(monthly)}\n")
    print(f"Monthly report completed: {len(monthly)} unique articles.")


if __name__ == "__main__":
    main()
