from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
import feedparser
import pandas as pd

from src.utils.classifier import classify_topic, detect_country
from src.utils.duplicate import clean_text

CAMBODIA_TZ = timezone(timedelta(hours=7))

CROPS = {
    "Mango": ["Cambodia mango export", "Cambodia mango market", "Cambodia mango price", "global mango market"],
    "Cashew": ["Cambodia cashew export", "Cambodia cashew market", "Cambodia cashew price", "global cashew market"],
    "Rice": ["Cambodia rice export", "Cambodia rice market", "Cambodia paddy price", "global rice market"],
    "Vegetables": ["Cambodia vegetable price", "Cambodia vegetable market", "Cambodia fresh vegetables", "global vegetable market"],
}

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

def collect_all_news():
    rows = []
    for crop, queries in CROPS.items():
        for query in queries:
            print(f"Collecting: {query}")
            rows.extend(google_news_rss(query, crop))
    return pd.DataFrame(rows)
