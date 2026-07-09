import os
import re
import hashlib
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.collectors.collector import collect_all_news
from src.drive.drive import upload_file, download_file_by_name
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


def clean_text(value):
    value = str(value or "").lower().strip()
    value = re.sub(r"<.*?>", " ", value)
    value = re.sub(r"[^a-z0-9\u1780-\u17ff]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_url(value):
    value = str(value or "").strip()
    return value.split("?")[0].split("#")[0]


def get_domain(value):
    try:
        domain = urlparse(str(value)).netloc.lower()
        domain = domain.replace("www.", "")
        return domain
    except Exception:
        return ""


def make_hash(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def add_duplicate_keys(df):
    if df.empty:
        return df

    if "url" not in df.columns:
        df["url"] = ""

    if "title" not in df.columns:
        df["title"] = ""

    df["clean_url"] = df["url"].apply(clean_url)
    df["source_domain"] = df["clean_url"].apply(get_domain)
    df["clean_title"] = df["title"].apply(clean_text)

    df["url_id"] = df["clean_url"].apply(make_hash)

    df["same_site_title_id"] = (
        df["source_domain"].astype(str)
        + "|"
        + df["clean_title"].astype(str)
    ).apply(make_hash)

    df["article_id"] = (
        df["clean_url"].astype(str)
        + "|"
        + df["source_domain"].astype(str)
        + "|"
        + df["clean_title"].astype(str)
    ).apply(make_hash)

    return df


def clean_duplicates(df):
    if df.empty:
        return df

    df = add_duplicate_keys(df)

    # Remove exact same URL
    df = df.drop_duplicates(subset=["url_id"])

    # Remove same website + same clean title
    df = df.drop_duplicates(subset=["same_site_title_id"])

    return df


def add_published_datetime(df):
    df["published_dt"] = pd.to_datetime(
        df.get("published_date", ""),
        errors="coerce",
        utc=True
    )

    df["published_dt_kh"] = df["published_dt"].dt.tz_convert(CAMBODIA_TZ)
    return df


def remove_timezone(df):
    for col in df.columns:
        if pd.api.types.is_datetime64tz_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)
    return df


def create_status_dataframe(today, run_time, message):
    return pd.DataFrame([
        {
            "date_collected": today,
            "run_time": run_time,
            "published_date": "",
            "crop": "",
            "country": "",
            "topic": "INFO",
            "title": message,
            "Summary": message,
            "source": "PEARL System",
            "language": "en",
            "url": "",
            "search_query": "",
            "status": "NO_NEW_NEWS"
        }
    ])


def main():
    os.makedirs(OUTPUT_DAILY, exist_ok=True)
    os.makedirs(OUTPUT_MASTER, exist_ok=True)
    os.makedirs(OUTPUT_LOGS, exist_ok=True)

    now = datetime.now(CAMBODIA_TZ)
    today = now.strftime("%Y-%m-%d")
    start_time = now - timedelta(hours=24)
    run_time = now.strftime("%Y-%m-%d %H:%M:%S")

    daily_csv = f"{OUTPUT_DAILY}/PEARL_daily_news_{today}.csv"
    daily_xlsx = f"{OUTPUT_DAILY}/PEARL_daily_news_{today}.xlsx"
    daily_docx = f"{OUTPUT_DAILY}/PEARL_daily_summary_{today}.docx"
    daily_log = f"{OUTPUT_LOGS}/PEARL_daily_log_{today}.txt"

    write_log("")
    write_log(f"===== PEARL Daily News Run Started: {run_time} =====")

    download_file_by_name(MASTER_FILENAME, MASTER_FILE)

    raw_count = 0
    recent_count = 0
    daily_unique_count = 0
    new_count = 0

    master = load_master()

    df = collect_all_news()

    if df.empty:
        status_message = "No news collected from RSS sources."
        export_df = create_status_dataframe(today, run_time, status_message)

    else:
        raw_count = len(df)

        df = add_published_datetime(df)

        df = df[
            df["published_dt_kh"].notna()
            & (df["published_dt_kh"] >= start_time)
            & (df["published_dt_kh"] <= now)
        ].copy()

        recent_count = len(df)

        if df.empty:
            status_message = "No news published in the last 24 hours."
            export_df = create_status_dataframe(today, run_time, status_message)

        else:
            df = clean_duplicates(df)
            df["Summary"] = df.apply(make_summary, axis=1)

            daily_unique_count = len(df)

            if not master.empty:
                master = clean_duplicates(master)

                existing_urls = set(master["url_id"].astype(str))
                existing_site_titles = set(master["same_site_title_id"].astype(str))

                new_df = df[
                    (~df["url_id"].astype(str).isin(existing_urls))
                    & (~df["same_site_title_id"].astype(str).isin(existing_site_titles))
                ].copy()
            else:
                new_df = df.copy()

            new_count = len(new_df)

            if new_df.empty:
                status_message = "No new unique news found in the last 24 hours."
                export_df = create_status_dataframe(today, run_time, status_message)
            else:
                export_df = new_df.copy()

            combined = pd.concat([master, new_df], ignore_index=True)
            combined = clean_duplicates(combined)
            combined.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")

    # If master does not exist yet, create empty master file
    if not os.path.exists(MASTER_FILE):
        master.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")

    export_df = remove_timezone(export_df.copy())

    export_df.to_csv(daily_csv, index=False, encoding="utf-8-sig")
    export_df.to_excel(daily_xlsx, index=False)

    create_daily_word_report(export_df, daily_docx, today)

    master_total = 0
    if os.path.exists(MASTER_FILE):
        try:
            master_total = len(pd.read_csv(MASTER_FILE))
        except Exception:
            master_total = 0

    with open(daily_log, "w", encoding="utf-8") as f:
        f.write("PEARL Daily News Log\n")
        f.write(f"Run time Cambodia: {run_time}\n")
        f.write(f"Raw collected articles: {raw_count}\n")
        f.write(f"Articles published in last 24 hours: {recent_count}\n")
        f.write(f"Daily unique after duplicate removal: {daily_unique_count}\n")
        f.write(f"New unique articles added to master: {new_count}\n")
        f.write(f"Master total records: {master_total}\n")

    upload_file(daily_csv)
    upload_file(daily_xlsx)
    upload_file(daily_docx)
    upload_file(MASTER_FILE, MASTER_FILENAME)
    upload_file(daily_log)

    write_log(f"Raw collected articles: {raw_count}")
    write_log(f"Articles published in last 24 hours: {recent_count}")
    write_log(f"Daily unique after duplicate removal: {daily_unique_count}")
    write_log(f"New unique articles added to master: {new_count}")
    write_log(f"Master total records: {master_total}")
    write_log("Daily collection completed successfully.")


if __name__ == "__main__":
    main()
