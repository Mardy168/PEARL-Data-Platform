from __future__ import annotations

import os
from pathlib import Path

from src.archive.manager import archive_weekly_run
from src.master.manager import MASTER_FILENAME, normalized_master_for_reporting
from src.reports.common import add_news_section, configure_document
from src.utils.dates import now_cambodia, remove_timezone_columns, rolling_window
from src.utils.excel import write_excel

DATA_ROOT = Path(os.getenv("PEARL_DATA_ROOT", "data"))
OUTPUT_WEEKLY = DATA_ROOT / "weekly"
OUTPUT_LOGS = DATA_ROOT / "logs"
MASTER_FILE = DATA_ROOT / "master" / MASTER_FILENAME


def main() -> None:
    OUTPUT_WEEKLY.mkdir(parents=True, exist_ok=True)
    OUTPUT_LOGS.mkdir(parents=True, exist_ok=True)
    now = now_cambodia()
    start, end = rolling_window(now, days=7)
    report_date = now.strftime("%Y-%m-%d")
    master = normalized_master_for_reporting(MASTER_FILE)
    weekly = master.loc[
        master["published_dt_kh"].notna()
        & (master["published_dt_kh"] >= start)
        & (master["published_dt_kh"] < end)
    ].sort_values("published_dt_kh", ascending=False).copy()
    xlsx = OUTPUT_WEEKLY / f"PEARL_weekly_news_{report_date}.xlsx"
    docx = OUTPUT_WEEKLY / f"PEARL_weekly_summary_{report_date}.docx"
    log = OUTPUT_LOGS / f"PEARL_weekly_log_{report_date}.txt"
    write_excel(remove_timezone_columns(weekly), str(xlsx))
    doc = configure_document("PEARL Weekly Agriculture News Summary", f"Rolling coverage: {start:%Y-%m-%d %H:%M:%S} to {end:%Y-%m-%d %H:%M:%S} (end exclusive)")
    cambodia = weekly.loc[weekly["country"].astype(str).str.lower().eq("cambodia")]
    global_news = weekly.loc[~weekly["country"].astype(str).str.lower().eq("cambodia")]
    add_news_section(doc, "Page 1: Cambodia News", cambodia, 12)
    doc.add_page_break()
    add_news_section(doc, "Page 2: Global News", global_news, 12)
    doc.save(docx)
    with log.open("w", encoding="utf-8") as handle:
        handle.write(f"Master records loaded: {len(master)}\nWeekly window: {start} to {end} (end exclusive)\n")
        handle.write(f"Unique articles: {len(weekly)}\nCambodia: {len(cambodia)}\nGlobal: {len(global_news)}\n")
    archived = archive_weekly_run(report_date=report_date, files=[xlsx, docx, log])
    print(archived.message)
    print(f"Weekly report completed: {len(weekly)} unique articles.")


if __name__ == "__main__":
    main()
