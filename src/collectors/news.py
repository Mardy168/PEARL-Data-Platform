import time
from urllib.parse import quote_plus
import feedparser
import requests


def google_news(query, limit=20):
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
            "summary": e.get("summary", "")
        })
    return rows


def gdelt_news(query, limit=50):
    api = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {"query": query, "mode": "ArtList", "format": "json", "maxrecords": limit, "sort": "HybridRel"}
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
            "summary": ""
        })
    return rows


def collect_news(crops):
    all_rows = []
    for crop, queries in crops.items():
        for query in queries:
            print(f"Collecting: {crop} | {query}")
            rows = google_news(query) + gdelt_news(query)
            for row in rows:
                row["crop"] = crop
                row["search_query"] = query
                all_rows.append(row)
            time.sleep(1)
    return all_rows
