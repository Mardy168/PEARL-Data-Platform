import time
from datetime import datetime, timezone
from urllib.parse import quote_plus
import feedparser
import requests


def google_news(query, limit=25):
    url = "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    rows = []
    for e in feed.entries[:limit]:
        rows.append({
            "published_date": e.get("published", ""),
            "title": e.get("title", ""),
            "source": "Google News RSS",
            "country": "",
            "language": "en",
            "url": e.get("link", ""),
            "summary": e.get("summary", ""),
            "collector": "google_news_rss"
        })
    return rows


def gdelt_news(query, limit=75):
    api = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": limit,
        "sort": "HybridRel"
    }
    try:
        r = requests.get(api, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"GDELT error for {query}: {e}")
        return []
    rows = []
    for a in data.get("articles", []):
        rows.append({
            "published_date": a.get("seendate", ""),
            "title": a.get("title", ""),
            "source": a.get("domain", ""),
            "country": a.get("sourcecountry", ""),
            "language": a.get("language", ""),
            "url": a.get("url", ""),
            "summary": "",
            "collector": "gdelt_doc"
        })
    return rows


def rss_source_news(source, crop_names, limit=30):
    rows = []
    try:
        feed = feedparser.parse(source["url"])
    except Exception as e:
        print(f"RSS error for {source.get('name')}: {e}")
        return rows
    for e in feed.entries[:limit]:
        title = e.get("title", "")
        summary = e.get("summary", "")
        text = f"{title} {summary}".lower()
        if not any(c.lower().replace('vegetables','vegetable') in text for c in crop_names):
            continue
        rows.append({
            "published_date": e.get("published", e.get("updated", "")),
            "title": title,
            "source": source.get("name", "RSS"),
            "country": "Cambodia" if source.get("group") == "Cambodia News" else "",
            "language": "",
            "url": e.get("link", ""),
            "summary": summary,
            "collector": "curated_rss",
            "source_group": source.get("group", "")
        })
    return rows


def collect_news(crops, rss_sources=None):
    all_rows = []
    for crop, queries in crops.items():
        for query in queries:
            print(f"Collecting news: {crop} | {query}")
            rows = google_news(query) + gdelt_news(query)
            for row in rows:
                row["crop"] = crop
                row["search_query"] = query
                all_rows.append(row)
            time.sleep(1)
    if rss_sources:
        crop_names = list(crops.keys())
        for source in rss_sources:
            print(f"Collecting curated RSS: {source.get('name')}")
            rows = rss_source_news(source, crop_names)
            for row in rows:
                row.setdefault("crop", "Unclassified")
                row.setdefault("search_query", source.get("name", "curated_rss"))
                all_rows.append(row)
            time.sleep(1)
    return all_rows
