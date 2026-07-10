from __future__ import annotations

from pathlib import Path
import pandas as pd

from src.drive.drive import download_file_by_name, upload_file
from src.reports.common import configure_document, add_news_section
from src.utils.dates import add_published_columns, now_cambodia, remove_timezone_columns, rolling_window
from src.utils.duplicate import deduplicate_articles
from src.utils.excel import write_excel

OUTPUT_WEEKLY = Path("data/weekly")
OUTPUT_LOGS = Path("data/logs")
MASTER_FILE = Path("data/master/PEARL_master_news.csv")
MASTER_FILENAME = MASTER_FILE.name


def main() -> None:
    OUTPUT_WEEKLY.mkdir(parents=True, exist_ok=True)
    OUTPUT_LOGS.mkdir(parents=True, exist_ok=True)
    MASTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    download_file_by_name(MASTER_FILENAME, str(MASTER_FILE))
    if not MASTER_FILE.exists():
        raise FileNotFoundError("Master file is missing. Run daily collector first.")

    now = now_cambodia()
    start, end = rolling_window(now, days=7)
    report_date = now.strftime("%Y-%m-%d")
    df = add_published_columns(pd.read_csv(MASTER_FILE))
    weekly = df[df["published_dt_kh"].notna() &
                (df["published_dt_kh"] >= start) &
                (df["published_dt_kh"] <= end)].copy()
    weekly = deduplicate_articles(weekly)
    weekly = weekly[weekly.get("status", "ARTICLE").astype(str).eq("ARTICLE")] if "status" in weekly.columns else weekly
    weekly = weekly.sort_values("published_dt_kh", ascending=False)

    xlsx = OUTPUT_WEEKLY / f"PEARL_weekly_news_{report_date}.xlsx"
    docx = OUTPUT_WEEKLY / f"PEARL_weekly_summary_{report_date}.docx"
    log = OUTPUT_LOGS / f"PEARL_weekly_log_{report_date}.txt"
    write_excel(remove_timezone_columns(weekly), str(xlsx))

    doc = configure_document("PEARL Weekly Agriculture News Summary",
                             f"Rolling coverage: {start.strftime('%Y-%m-%d %H:%M:%S')} to {end.strftime('%Y-%m-%d %H:%M:%S')}")
    cambodia = weekly[weekly["country"].astype(str).str.lower().eq("cambodia")]
    global_news = weekly[~weekly["country"].astype(str).str.lower().eq("cambodia")]
    add_news_section(doc, "Page 1: Cambodia News", cambodia, 12)
    doc.add_page_break()
    add_news_section(doc, "Page 2: Global News", global_news, 12)
    doc.save(docx)

    with open(log, "w", encoding="utf-8") as f:
        f.write(f"Weekly window: {start} to {end}\n")
        f.write(f"Unique articles: {len(weekly)}\nCambodia: {len(cambodia)}\nGlobal: {len(global_news)}\n")
    for path in (xlsx, docx, log): upload_file(str(path))
    print("Weekly report completed successfully.")


if __name__ == "__main__":
    main()
