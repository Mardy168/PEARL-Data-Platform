import os
import re
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import pandas as pd

from src.drive.upload import upload_file


CAMBODIA_TZ = timezone(timedelta(hours=7))
OUTPUT_DAILY = "data/daily"
OUTPUT_MASTER = "data/master"
MASTER_FILE = f"{OUTPUT_MASTER}/PEARL_master_news.csv"


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
    "Market": ["market", "price", "demand", "supply", "buyer", "seller"],
    "Export": ["export", "shipment", "trade", "china", "vietnam", "eu", "japan"],
    "Production": ["production", "harvest", "yield", "farmer", "cultivation"],
    "Climate Risk": ["drought", "flood", "rain", "climate", "heat", "weather"],
    "Policy": ["policy", "ministry", "government", "strategy", "regulation"],
    "Investment": ["investment", "factory", "processing", "loan", "finance"],
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
    found = [topic for topic, keys in TOPIC_KEYWORDS.items() if any(k in text for k in keys)]
    return "; ".join(found) if found else "General"


def detect_country(text):
    text = text.lower()
    if "cambodia" in text or "phnom penh" in text:
        return "Cambodia"
    return "Global"


def make_summary(row):
    title = clean_text(row.get("title", ""))
    crop = row.get("crop", "")
    topic = row.get("topic", "General")
    country = row.get("country", "Global")

    return (
        f"{country} {crop} update related to {topic.lower()}. "
        f"Key news: {title}"
    )[:500]


def google_news_rss(query, crop):
    url = "https://news.google.com/rss/search?q=" + quote_plus(query)
    feed = feedparser.parse(url)

    rows = []
    for entry in feed.entries[:50]:
        title = clean_text(entry.get("title", ""))
        summary_raw = clean_text(entry.get("summary", ""))
        link = entry.get("link", "")

        published = ""
        if getattr(entry, "published", None):
            published = entry.published

        text_all = f"{title} {summary_raw}"

        rows.append({
            "date_collected": datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d"),
            "published_date": published,
            "crop": crop,
            "country": detect_country(text_all),
            "topic": classify_topic(text_all),
            "title": title,
            "Summary": "",
            "source": "Google News RSS",
            "language": "en",
            "url": link,
            "search_query": query,
            "summary_raw": summary_raw,
        })

    return rows


def load_master():
    if os.path.exists(MASTER_FILE):
        return pd.read_csv(MASTER_FILE)
    return pd.DataFrame()


def main():
    os.makedirs(OUTPUT_DAILY, exist_ok=True)
    os.makedirs(OUTPUT_MASTER, exist_ok=True)

    today = datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d")
    rows = []

    for crop, queries in CROPS.items():
        for query in queries:
            print(f"Collecting: {query}")
            rows.extend(google_news_rss(query, crop))

    df = pd.DataFrame(rows)

    if df.empty:
        print("No news collected.")
        return

    df["article_id"] = df["url"].fillna(df["title"]).apply(make_hash)
    df = df.drop_duplicates(subset=["article_id"])
    df["Summary"] = df.apply(make_summary, axis=1)

    master = load_master()

    if not master.empty and "article_id" in master.columns:
        existing = set(master["article_id"].astype(str))
        new_df = df[~df["article_id"].astype(str).isin(existing)].copy()
    else:
        new_df = df.copy()

    print(f"Collected: {len(df)}")
    print(f"New unique articles: {len(new_df)}")

    combined = pd.concat([master, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["article_id"])
    combined.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")

    csv_path = f"{OUTPUT_DAILY}/PEARL_daily_news_{today}.csv"
    xlsx_path = f"{OUTPUT_DAILY}/PEARL_daily_news_{today}.xlsx"

    new_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    new_df.to_excel(xlsx_path, index=False)

    upload_file(csv_path)
    upload_file(xlsx_path)

    print("Daily collection completed and uploaded.")


if __name__ == "__main__":
    main()
