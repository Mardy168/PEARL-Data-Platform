import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.collectors.collector import collect_all_news
from src.drive.drive import upload_file, download_file_by_name
from src.utils.duplicate import add_duplicate_keys, remove_similar_titles
from src.utils.summarizer import make_summary
from src.reports.daily import create_daily_word_report


CAMBODIA_TZ = timezone(timedelta(hours=7))

OUTPUT_DAILY = "data/daily"
OUTPUT_MASTER = "data/master"
OUTPUT_LOGS = "data/logs"

MASTER_FILENAME = "PEARL_master_news.csv"
MASTER_FILE = f"{OUTPUT_MASTER}/{MASTER_FILENAME}"


def load_master():
    if os.path.exists(MASTER_FILE):
        return pd.read_csv(MASTER_FILE)
    return pd.DataFrame()


def write_log(message):
    os.makedirs(OUTPUT_LOGS, exist_ok=True)
    with open(f"{OUTPUT_LOGS}/daily_log.txt", "a", encoding="utf-8") as f:
        f.write(message + "\n")
    print(message)


def main():
    os.makedirs(OUTPUT_DAILY, exist_ok=True)
    os.makedirs(OUTPUT_MASTER, exist_ok=True)
    os.makedirs(OUTPUT_LOGS, exist_ok=True)

    today = datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d")
    run_time = datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d %H:%M:%S")

    write_log("")
    write_log(f"===== PEARL Daily News Run Started: {run_time} =====")

    downloaded = download_file_by_name(MASTER_FILENAME, MASTER_FILE)

    if downloaded:
        write_log("Master database downloaded from Google Drive.")
    else:
        write_log("No existing master database found. Creating a new one.")

    df = collect_all_news()

    if df.empty:
        write_log("No news collected.")
        return

    raw_count = len(df)

    df = add_duplicate_keys(df)
    df = df.drop_duplicates(subset=["title_id"])
    df = df.drop_duplicates(subset=["url_id"])
    df = remove_similar_titles(df, threshold=0.92)

    df["Summary"] = df.apply(make_summary, axis=1)

    daily_unique_count = len(df)

    master = load_master()

    if not master.empty:
        master = add_duplicate_keys(master)

        existing_titles = set(master["title_id"].astype(str))
        existing_urls = set(master["url_id"].astype(str))

        new_df = df[
            (~df["title_id"].astype(str).isin(existing_titles)) &
            (~df["url_id"].astype(str).isin(existing_urls))
        ].copy()
    else:
        new_df = df.copy()

    combined = pd.concat([master, new_df], ignore_index=True)
    combined = add_duplicate_keys(combined)
    combined = combined.drop_duplicates(subset=["title_id"])
    combined = combined.drop_duplicates(subset=["url_id"])
    combined = remove_similar_titles(combined, threshold=0.92)

    combined.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")

    daily_csv = f"{OUTPUT_DAILY}/PEARL_daily_news_{today}.csv"
    daily_xlsx = f"{OUTPUT_DAILY}/PEARL_daily_news_{today}.xlsx"
    daily_docx = f"{OUTPUT_DAILY}/PEARL_daily_summary_{today}.docx"
    daily_log = f"{OUTPUT_LOGS}/PEARL_daily_log_{today}.txt"

    # Daily output = unique daily news after duplicate cleaning
    df.to_csv(daily_csv, index=False, encoding="utf-8-sig")
    df.to_excel(daily_xlsx, index=False)

    # Daily Word = one page, Cambodia half + Global half, no links
    create_daily_word_report(df, daily_docx, today)

    with open(daily_log, "w", encoding="utf-8") as f:
        f.write("PEARL Daily News Log\n")
        f.write(f"Run time Cambodia: {run_time}\n")
        f.write(f"Raw collected articles: {raw_count}\n")
        f.write(f"Daily unique articles: {daily_unique_count}\n")
        f.write(f"New unique articles added to master: {len(new_df)}\n")
        f.write(f"Master total records: {len(combined)}\n")

    upload_file(daily_csv)
    upload_file(daily_xlsx)
    upload_file(daily_docx)
    upload_file(MASTER_FILE, MASTER_FILENAME)
    upload_file(daily_log)

    write_log(f"Raw collected articles: {raw_count}")
    write_log(f"Daily unique articles: {daily_unique_count}")
    write_log(f"New unique articles added to master: {len(new_df)}")
    write_log(f"Master total records: {len(combined)}")
    write_log("Daily collection completed successfully.")


if __name__ == "__main__":
    main()
