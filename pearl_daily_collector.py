import os
import re
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import pandas as pd

from src.drive.upload import upload_file


CAMBODIA_TZ = timezone(timedelta(hours=7))
OUTPUT_DIR = "data/daily"
MASTER_FILE = "data/master/PEARL_master_news.csv"

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
    "Market": ["market", "price", "demand", "supply", "buyer", "trade"],
    "Export": ["export", "shipment", "china", "vietnam", "eu", "trade"],
    "Production": ["production", "harvest", "yield", "farm", "cultivation"],
    "Climate": ["drought", "flood", "rain", "climate", "heat", "weather"],
    "Policy": ["policy", "government", "ministry", "strategy", "regulation"],
    "Investment": ["investment", "loan", "finance", "factory", "processing"],
    "Pest/Disease": ["pest", "disease", "outbreak"],
}


def clean_text(text):
    text = re.sub(r"<.*?>", " ", str(text))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_hash(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def classify_topic(text):
    text = text.lower()
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(k in text for k in keywords):
            topics.append(topic)
    return "; ".join(topics) if topics else "General"


def make_summary(row):
    title = clean_text(row.get("title", ""))
    crop = row.get("crop", "")
    topic = row.get("topic", "General")

    if not title:
        return ""

    return f"{crop} news related to {topic.lower()}: {title}"[:450]


def parse_date(entry):
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def google_news_rss(query, crop):
    url = "https://news.google.com/rss/search?q=" + quote_plus(query)
    feed = feedparser.parse(url)

    rows = []
    for entry in feed.entries[:50]:
        published_dt = parse_date(entry)

        rows.append({
            "date_collected": datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d"),
            "published_date": published_dt.strftime("%Y-%m-%d %H:%M:%S UTC") if published_dt else "",
            "crop": crop,
            "search_query": query,
            "title": clean_text(entry.get("title", "")),
            "source": "Google News RSS",
            "language": "en",
            "url": entry.get("link", ""),
            "summary_raw": clean_text(entry.get("summary", "")),
        })

    return rows


def load_master():
    if os.path.exists(MASTER_FILE):
        return pd.read_csv(MASTER_FILE)
    return pd.DataFrame()


def save_master(df):
    os.makedirs(os.path.dirname(MASTER_FILE), exist_ok=True)
    df.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today = datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d")
    all_rows = []

    for crop, queries in CROPS.items():
        for query in queries:
            print(f"Collecting: {query}")
            all_rows.extend(google_news_rss(query, crop))

    df = pd.DataFrame(all_rows)

    if df.empty:
        print("No articles collected.")
        return

    df["article_id"] = df["url"].fillna(df["title"]).apply(make_hash)
    df["topic"] = (df["title"].fillna("") + " " + df["summary_raw"].fillna("")).apply(classify_topic)
    df["Summary"] = df.apply(make_summary, axis=1)

    df = df.drop_duplicates(subset=["article_id"])

    master = load_master()

    if not master.empty and "article_id" in master.columns:
        existing_ids = set(master["article_id"].astype(str))
        new_df = df[~df["article_id"].astype(str).isin(existing_ids)].copy()
    else:
        new_df = df.copy()

    print(f"Total collected: {len(df)}")
    print(f"New unique articles: {len(new_df)}")

    combined = pd.concat([master, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["article_id"])
    save_master(combined)

    csv_path = f"{OUTPUT_DIR}/PEARL_daily_news_{today}.csv"
    xlsx_path = f"{OUTPUT_DIR}/PEARL_daily_news_{today}.xlsx"

    new_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    new_df.to_excel(xlsx_path, index=False)

    upload_file(csv_path)
    upload_file(xlsx_path)

    print("Daily collection completed.")


if __name__ == "__main__":
    main()
