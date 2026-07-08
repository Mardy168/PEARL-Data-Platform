import os
import re
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import pandas as pd

from src.drive.upload import upload_file, download_file_by_name


CAMBODIA_TZ = timezone(timedelta(hours=7))

OUTPUT_DAILY = "data/daily"
OUTPUT_MASTER = "data/master"

MASTER_FILENAME = "PEARL_master_news.csv"
MASTER_FILE = f"{OUTPUT_MASTER}/{MASTER_FILENAME}"


CROPS = {
    "Mango": [
        "Cambodia mango export",
        "Cambodia mango market",
        "Cambodia mango price",
        "global mango market",
    ],
    "Cashew": [
        "Cambodia cashew export",
        "Cambodia cashew market",
        "Cambodia cashew price",
        "global cashew market",
    ],
    "Rice": [
        "Cambodia rice export",
        "Cambodia rice market",
        "Cambodia paddy price",
        "global rice market",
    ],
    "Vegetables": [
        "Cambodia vegetable price",
        "Cambodia vegetable market",
        "Cambodia fresh vegetables",
        "global vegetable market",
    ],
}


TOPIC_KEYWORDS = {
    "Market": ["market", "price", "demand", "supply", "buyer", "seller", "retail"],
    "Export": ["export", "shipment", "trade", "china", "vietnam", "eu", "japan", "import"],
    "Production": ["production", "harvest", "yield", "farmer", "cultivation", "crop"],
    "Climate Risk": ["drought", "flood", "rain", "climate", "heat", "weather", "storm"],
    "Policy": ["policy", "ministry", "government", "strategy", "regulation", "law"],
    "Investment": ["investment", "factory", "processing", "loan", "finance", "credit"],
    "Pest/Disease": ["pest", "disease", "outbreak", "insect"],
}


def clean_text(text):
    text = re.sub(r"<.*?>", " ", str(text))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(title):
    title = clean_text(title).lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def normalize_url(url):
    url = str(url).strip()
    url = url.split("&")[0]
    url = url.split("?")[0]
    return url.strip()


def make_hash(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def classify_topic(text):
    text = str(text).lower()
    topics = []

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            topics.append(topic)

    return "; ".join(topics) if topics else "General"


def detect_country(text):
    text = str(text).lower()

    if "cambodia" in text or "phnom penh" in text or "khmer" in text:
        return "Cambodia"

    return "Global"


def make_summary(row):
    title = clean_text(row.get("title", ""))
    crop = row.get("crop", "")
    topic = row.get("topic", "General")
    country = row.get("country", "Global")

    if not title:
        return ""

    return (
        f"{country} {crop} news related to {str(topic).lower()}. "
        f"Key point: {title}"
    )[:500]


def google_news_rss(query, crop):
    rss_url = "https://news.google.com/rss/search?q=" + quote_plus(query)
    feed = feedparser.parse(rss_url)

    rows = []

    for entry in feed.entries[:50]:
        title = clean_text(entry.get("title", ""))
        summary_raw = clean_text(entry.get("summary", ""))
        url = entry.get("link", "")
        published = entry.get("published", "")

        text_all = f"{title} {summary_raw}"

        rows.append({
            "date_collected": datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d"),
            "run_time_cambodia": datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "published_date": published,
            "crop": crop,
            "country": detect_country(text_all),
            "topic": classify_topic(text_all),
            "title": title,
            "Summary": "",
            "source": "Google News RSS",
            "language": "en",
            "url": url,
            "search_query": query,
            "summary_raw": summary_raw,
        })

    return rows


def load_master():
    if os.path.exists(MASTER_FILE):
        return pd.read_csv(MASTER_FILE)

    return pd.DataFrame()


def ensure_required_columns(df):
    for col in ["title", "url"]:
        if col not in df.columns:
            df[col] = ""

    df["clean_title"] = df["title"].apply(normalize_title)
    df["clean_url"] = df["url"].apply(normalize_url)

    df["title_id"] = df["clean_title"].apply(make_hash)
    df["url_id"] = df["clean_url"].apply(make_hash)

    df["article_id"] = df["title_id"]

    return df


def main():
    os.makedirs(OUTPUT_DAILY, exist_ok=True)
    os.makedirs(OUTPUT_MASTER, exist_ok=True)

    today = datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d")

    download_file_by_name(MASTER_FILENAME, MASTER_FILE)

    rows = []

    for crop, queries in CROPS.items():
        for query in queries:
            print(f"Collecting: {query}")
            rows.extend(google_news_rss(query, crop))

    df = pd.DataFrame(rows)

    if df.empty:
        print("No news collected.")
        return

    df = ensure_required_columns(df)

    df = df.drop_duplicates(subset=["title_id"])
    df = df.drop_duplicates(subset=["url_id"])

    df["Summary"] = df.apply(make_summary, axis=1)

    master = load_master()

    if not master.empty:
        master = ensure_required_columns(master)

        existing_titles = set(master["title_id"].astype(str))
        existing_urls = set(master["url_id"].astype(str))

        new_df = df[
            (~df["title_id"].astype(str).isin(existing_titles)) &
            (~df["url_id"].astype(str).isin(existing_urls))
        ].copy()
    else:
        new_df = df.copy()

    print(f"Collected after internal deduplication: {len(df)}")
    print(f"New unique articles compared with master: {len(new_df)}")

    combined = pd.concat([master, new_df], ignore_index=True)
    combined = ensure_required_columns(combined)
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

    print("Daily collection completed.")
    print(f"Daily CSV: {daily_csv}")
    print(f"Daily Excel: {daily_xlsx}")
    print(f"Master updated: {MASTER_FILE}")


if __name__ == "__main__":
    main()
