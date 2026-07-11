from __future__ import annotations

from pathlib import Path

from src.drive.drive import resolve_subfolder, upload_file
from src.master.manager import MASTER_FILENAME, load_master_safely
from src.reports.common import add_news_section, configure_document
from src.utils.dates import add_published_columns, now_cambodia, remove_timezone_columns, rolling_window
from src.utils.duplicate import deduplicate_articles
from src.utils.excel import write_excel

OUTPUT_WEEKLY = Path("data/weekly")
OUTPUT_LOGS = Path("data/logs")
MASTER_FILE = Path("data/master") / MASTER_FILENAME


def main() -> None:
    OUTPUT_WEEKLY.mkdir(parents=True, exist_ok=True)
    OUTPUT_LOGS.mkdir(parents=True, exist_ok=True)
    MASTER_FILE.parent.mkdir(parents=True, exist_ok=True)

    state = load_master_safely(MASTER_FILE, create_backup=False)
    now = now_cambodia()
    start, end = rolling_window(now, days=7)
    report_date = now.strftime("%Y-%m-%d")
    df = add_published_columns(state.dataframe.copy())
    weekly = df[
        df["published_dt_kh"].notna()
        & (df["published_dt_kh"] >= start)
        & (df["published_dt_kh"] <= end)
    ].copy()
    weekly = deduplicate_articles(weekly)
    weekly = weekly[weekly["status"].astype(str).eq("ARTICLE")]
    weekly = weekly.sort_values("published_dt_kh", ascending=False)

    xlsx = OUTPUT_WEEKLY / f"PEARL_weekly_news_{report_date}.xlsx"
    docx = OUTPUT_WEEKLY / f"PEARL_weekly_summary_{report_date}.docx"
    log = OUTPUT_LOGS / f"PEARL_weekly_log_{report_date}.txt"
    write_excel(remove_timezone_columns(weekly), str(xlsx))

    doc = configure_document(
        "PEARL Weekly Agriculture News Summary",
        f"Rolling coverage: {start:%Y-%m-%d %H:%M:%S} to {end:%Y-%m-%d %H:%M:%S}",
    )
    cambodia = weekly[weekly["country"].astype(str).str.lower().eq("cambodia")]
    global_news = weekly[~weekly["country"].astype(str).str.lower().eq("cambodia")]
    add_news_section(doc, "Page 1: Cambodia News", cambodia, 12)
    doc.add_page_break()
    add_news_section(doc, "Page 2: Global News", global_news, 12)
    doc.save(docx)

    with open(log, "w", encoding="utf-8") as fh:
        fh.write(f"Master Drive File ID: {state.file_id}\n")
        fh.write(f"Master records loaded: {state.record_count}\n")
        fh.write(f"Weekly window: {start} to {end}\n")
        fh.write(f"Unique articles: {len(weekly)}\n")
        fh.write(f"Cambodia: {len(cambodia)}\nGlobal: {len(global_news)}\n")

    weekly_folder = resolve_subfolder("Weekly")
    logs_folder = resolve_subfolder("Logs")
    upload_file(str(xlsx), folder_id=weekly_folder)
    upload_file(str(docx), folder_id=weekly_folder)
    upload_file(str(log), folder_id=logs_folder)
    print("Weekly report completed successfully.")


if __name__ == "__main__":
    main()
