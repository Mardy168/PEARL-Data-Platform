from __future__ import annotations

from pathlib import Path
import pandas as pd

from src.collectors.collector import collect_all_news_with_diagnostics
from src.drive.drive import upload_file
from src.master.manager import (
    MASTER_FILENAME,
    combine_and_validate_master,
    load_master_safely,
    save_master_transaction,
)
from src.reports.daily import create_daily_word_report
from src.utils.dates import add_published_columns, now_cambodia, remove_timezone_columns, rolling_window
from src.utils.duplicate import deduplicate_articles, exclude_existing
from src.utils.excel import write_excel, write_qa_workbook
from src.utils.summarizer import make_summary

DAILY = Path("data/daily")
MASTER_DIR = Path("data/master")
LOGS = Path("data/logs")
QA = Path("data/qa")
MASTER = MASTER_DIR / MASTER_FILENAME


def status_frame(now, message):
    return pd.DataFrame([{
        "date_collected": now.strftime("%Y-%m-%d"),
        "run_time_cambodia": now.strftime("%Y-%m-%d %H:%M:%S"),
        "Published Date": "",
        "crop": "",
        "country": "",
        "topic": "INFO",
        "title": message,
        "Summary": message,
        "publisher_name": "PEARL System",
        "publisher_domain": "",
        "source_type": "System",
        "source_name": "PEARL System",
        "language": "en",
        "url": "",
        "canonical_url": "",
        "google_news_url": "",
        "search_query": "",
        "article_id": "",
        "status": "NO_NEW_NEWS",
    }])


def main():
    for path in (DAILY, MASTER_DIR, LOGS, QA):
        path.mkdir(parents=True, exist_ok=True)

    now = now_cambodia()
    start, end = rolling_window(now, hours=24)
    label = now.strftime("%Y-%m-%d")
    csv_path = DAILY / f"PEARL_daily_news_{label}.csv"
    xlsx_path = DAILY / f"PEARL_daily_news_{label}.xlsx"
    docx_path = DAILY / f"PEARL_daily_summary_{label}.docx"
    log_path = LOGS / f"PEARL_daily_log_{label}.txt"
    qa_path = QA / f"PEARL_daily_QA_{label}.xlsx"

    # Critical safety behavior: missing/unreadable master aborts the run.
    state = load_master_safely(MASTER, create_backup=True)
    master = state.dataframe
    raw, source_health = collect_all_news_with_diagnostics()

    stats = {
        "Run Time Cambodia": now.strftime("%Y-%m-%d %H:%M:%S"),
        "Window Start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "Window End": end.strftime("%Y-%m-%d %H:%M:%S"),
        "Master Drive File ID": state.file_id,
        "Master Backup": state.backup_name or "Not created",
        "Master Before Run": state.record_count,
        "Sources Configured": len(source_health),
        "Sources Successful": int(source_health.get("success", pd.Series(dtype=bool)).fillna(False).sum()),
        "Raw Articles": len(raw),
        "Invalid Dates": 0,
        "Outside Window": 0,
        "Inside Window": 0,
        "Unique Inside Window": 0,
        "Already In Master": 0,
        "New Articles": 0,
        "Master After Run": state.record_count,
        "Master Validation": "Pending",
    }

    new_articles = pd.DataFrame()
    if raw.empty:
        export = status_frame(now, "No news collected from configured sources.")
    else:
        raw = add_published_columns(raw)
        stats["Invalid Dates"] = int(raw["published_dt_kh"].isna().sum())
        window = raw[
            raw["published_dt_kh"].notna()
            & (raw["published_dt_kh"] >= start)
            & (raw["published_dt_kh"] <= end)
        ].copy()
        stats["Inside Window"] = len(window)
        stats["Outside Window"] = len(raw) - stats["Invalid Dates"] - len(window)

        unique = deduplicate_articles(window)
        stats["Unique Inside Window"] = len(unique)
        if not unique.empty:
            unique["Summary"] = unique.apply(make_summary, axis=1)
        new_articles = exclude_existing(unique, master)
        stats["Already In Master"] = len(unique) - len(new_articles)
        stats["New Articles"] = len(new_articles)
        export = (
            new_articles
            if not new_articles.empty
            else status_frame(now, "No new unique news found in the last 24 hours.")
        )

    if not new_articles.empty:
        combined = combine_and_validate_master(master, new_articles)
        save_master_transaction(state, combined, local_path=MASTER)
        stats["Master After Run"] = len(combined)
    else:
        # Do not rewrite the master when nothing changed.
        stats["Master After Run"] = state.record_count
    stats["Master Validation"] = "PASSED"

    clean = remove_timezone_columns(export.copy())
    clean.to_csv(csv_path, index=False, encoding="utf-8-sig")
    write_excel(clean, str(xlsx_path))
    create_daily_word_report(clean, str(docx_path), label)
    write_qa_workbook(stats, source_health, str(qa_path))

    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("PEARL Daily News QA Log\n")
        for key, value in stats.items():
            fh.write(f"{key}: {value}\n")

    for path in (csv_path, xlsx_path, docx_path, log_path, qa_path):
        upload_file(str(path))
    print("Daily collection completed successfully with safe master protection.")


if __name__ == "__main__":
    main()
