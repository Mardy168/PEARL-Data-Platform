import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.collector import collect_all_news
from src.duplicate import add_duplicate_keys
from src.summarizer import make_summary
from src.drive import upload_file, download_file_by_name


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
    log_path = f"{OUTPUT_LOGS}/daily_log.txt"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(message + "\n")

    print(message)


def main():
    os.makedirs(OUTPUT_DAILY, exist_ok=True)
    os.makedirs(OUTPUT_MASTER, exist_ok=True)
    os.makedirs(OUTPUT_LOGS, exist_ok=True)

    today = datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d")

    write_log(f"===== Daily run started: {today} =====")

    download_file_by_name(MASTER_FILENAME, MASTER_FILE)

    df = collect_all_news()

    if df.empty:
        write_log("No news collected.")
        return

    df = add_duplicate_keys(df)
    df = df.drop_duplicates(subset=["title_id"])
    df = df.drop_duplicates(subset=["url_id"])

    df["Summary"] = df.apply(make_summary, axis=1)

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

    combined.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")

    daily_csv = f"{OUTPUT_DAILY}/PEARL_daily_news_{today}.csv"
    daily_xlsx = f"{OUTPUT_DAILY}/PEARL_daily_news_{today}.xlsx"

    new_df.to_csv(daily_csv, index=False, encoding="utf-8-sig")
    new_df.to_excel(daily_xlsx, index=False)

    upload_file(daily_csv)
    upload_file(daily_xlsx)
    upload_file(MASTER_FILE, MASTER_FILENAME)

    write_log(f"Collected total after internal deduplication: {len(df)}")
    write_log(f"New unique articles: {len(new_df)}")
    write_log(f"Master total records: {len(combined)}")
    write_log("Daily collection completed.")


if __name__ == "__main__":
    main()
