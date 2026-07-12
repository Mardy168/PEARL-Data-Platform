from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from src.collectors.collector import collect_all_news_with_diagnostics
from src.master.manager import MASTER_FILENAME, combine_and_validate_master, load_master_safely, save_master_transaction
from src.reports.daily import create_daily_word_report
from src.utils.dates import add_published_columns, daily_window, now_cambodia, remove_timezone_columns
from src.utils.duplicate import deduplicate_articles, exclude_existing
from src.utils.excel import write_excel, write_qa_workbook
from src.utils.summarizer import make_summary

DATA_ROOT = Path(os.getenv("PEARL_DATA_ROOT", "data"))
MASTER_PATH = DATA_ROOT / "master" / MASTER_FILENAME
DAILY_DIR = DATA_ROOT / "daily"
QA_DIR = DATA_ROOT / "qa"
LOG_DIR = DATA_ROOT / "logs"
RAW_DIR = DATA_ROOT / "raw_archive"
BOUNDARY_HOUR = int(os.getenv("DAILY_BOUNDARY_HOUR", "9"))


def _status_row(today: str, run_time: str, message: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "date_collected": today, "run_time_cambodia": run_time, "published_date": "",
        "crop": "", "country": "", "topic": "INFO", "title": message, "Summary": message,
        "publisher_name": "PEARL System", "publisher_domain": "", "source_type": "System",
        "source_name": "PEARL System", "language": "en", "url": "", "google_news_url": "",
        "search_query": "", "status": "NO_NEW_NEWS", "master_status": "NOT_APPLICABLE",
    }])


def main() -> None:
    for directory in (MASTER_PATH.parent, DAILY_DIR, QA_DIR, LOG_DIR, RAW_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    now = now_cambodia()
    today = now.strftime("%Y-%m-%d")
    run_time = now.strftime("%Y-%m-%d %H:%M:%S")
    start, end = daily_window(now, boundary_hour=BOUNDARY_HOUR)
    state = load_master_safely(MASTER_PATH, create_backup=True)
    raw, diagnostics = collect_all_news_with_diagnostics()
    raw_count = len(raw)
    raw_csv = RAW_DIR / f"PEARL_raw_news_{today}_{now:%H%M%S}.csv"
    raw.to_csv(raw_csv, index=False, encoding="utf-8-sig")
    invalid_dates = inside_count = unique_inside_count = new_count = 0
    master_after = state.dataframe
    if raw.empty:
        report_df = _status_row(today, run_time, "No articles were returned by the configured RSS sources.")
    else:
        enriched = add_published_columns(raw)
        invalid_dates = int(enriched["published_dt_kh"].isna().sum())
        inside = enriched.loc[
            enriched["published_dt_kh"].notna()
            & (enriched["published_dt_kh"] >= start)
            & (enriched["published_dt_kh"] < end)
        ].copy()
        inside_count = len(inside)
        inside = deduplicate_articles(inside)
        unique_inside_count = len(inside)
        if inside.empty:
            report_df = _status_row(today, run_time, "No news was published within the completed 24-hour window.")
        else:
            inside["Summary"] = inside.apply(make_summary, axis=1)
            new_articles = exclude_existing(inside, state.dataframe)
            new_count = len(new_articles)
            if new_articles.empty:
                report_df = _status_row(today, run_time, "No new unique news was found in the completed 24-hour window.")
            else:
                new_articles["master_status"] = "NEW"
                report_df = new_articles.sort_values("published_dt_kh", ascending=False)
                master_after = combine_and_validate_master(state.dataframe, new_articles)
                save_master_transaction(state, master_after, local_path=MASTER_PATH)
    daily_csv = DAILY_DIR / f"PEARL_daily_news_{today}.csv"
    daily_xlsx = DAILY_DIR / f"PEARL_daily_news_{today}.xlsx"
    daily_docx = DAILY_DIR / f"PEARL_daily_summary_{today}.docx"
    qa_xlsx = QA_DIR / f"PEARL_daily_QA_{today}.xlsx"
    log_txt = LOG_DIR / f"PEARL_daily_log_{today}.txt"
    export_df = remove_timezone_columns(report_df.copy())
    export_df.to_csv(daily_csv, index=False, encoding="utf-8-sig")
    write_excel(export_df, str(daily_xlsx))
    create_daily_word_report(export_df, str(daily_docx), today)
    metrics = {
        "Run Time Cambodia": run_time, "Window Start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "Window End Exclusive": end.strftime("%Y-%m-%d %H:%M:%S"),
        "Master Backup": state.backup_name or "", "Master Before Run": state.record_count,
        "Sources Configured": len(diagnostics),
        "Sources Successful": int(diagnostics.get("success", pd.Series(dtype=bool)).fillna(False).sum()),
        "Sources Possibly Truncated": int(diagnostics.get("possibly_truncated", pd.Series(dtype=bool)).fillna(False).sum()),
        "Raw Articles": raw_count, "Invalid Dates": invalid_dates, "Inside Window": inside_count,
        "Unique Inside Window": unique_inside_count, "New Articles Added": new_count,
        "Master After Run": len(master_after), "Master Validation": "PASSED",
    }
    write_qa_workbook(metrics, diagnostics, str(qa_xlsx))
    with log_txt.open("w", encoding="utf-8") as handle:
        for key, value in metrics.items():
            handle.write(f"{key}: {value}\n")
    print(f"Daily collection completed: {unique_inside_count} unique in window, {new_count} new to master.")


if __name__ == "__main__":
    main()
