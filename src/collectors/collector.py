from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import feedparser
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils.classifier import classify_topic, detect_country
from src.utils.dates import now_cambodia
from src.utils.duplicate import clean_text

ROOT = Path(__file__).resolve().parents[2]
KEYWORDS_FILE = ROOT / "config" / "keywords.json"
SOURCES_FILE = ROOT / "config" / "sources.json"
USER_AGENT = "PEARL-News-Collector/4.0 (+agricultural-monitoring; contact=repository-owner)"
REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_MAX_ITEMS = 100


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def _fetch_feed(url: str) -> tuple[feedparser.FeedParserDict, str]:
    try:
        response = _session().get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return feedparser.parse(response.content), ""
    except requests.RequestException as exc:
        return feedparser.FeedParserDict(entries=[]), f"{type(exc).__name__}: {exc}"


def _publisher_from_entry(entry, title: str, fallback: str = "") -> tuple[str, str]:
    source = entry.get("source", {}) or {}
    name = clean_text(source.get("title", "")) if isinstance(source, dict) else ""
    href = source.get("href", "") if isinstance(source, dict) else ""
    domain = urlparse(href).netloc.lower().removeprefix("www.") if href else ""
    if not name and " - " in title:
        name = clean_text(title.rsplit(" - ", 1)[-1])
    return name or fallback or "Unknown Publisher", domain


def _published_value(entry) -> str:
    return str(entry.get("published") or entry.get("updated") or entry.get("created") or "")


def _base_row(entry, crop: str, query: str, source_type: str, source_name: str, source_url: str = "") -> dict:
    now = now_cambodia()
    raw_title = clean_text(entry.get("title", ""))
    summary_raw = clean_text(entry.get("summary", entry.get("description", "")))
    link = str(entry.get("link", "") or "").strip()
    publisher, domain = _publisher_from_entry(entry, raw_title, source_name)
    if not domain and source_type == "Curated RSS":
        domain = urlparse(source_url).netloc.lower().removeprefix("www.")
    display_title = raw_title
    suffix = " - " + publisher
    if publisher and raw_title.lower().endswith(suffix.lower()):
        display_title = raw_title[: -len(suffix)].strip()
    all_text = f"{display_title} {summary_raw} {publisher}"
    return {
        "date_collected": now.strftime("%Y-%m-%d"),
        "run_time_cambodia": now.strftime("%Y-%m-%d %H:%M:%S"),
        "published_date": _published_value(entry),
        "crop": crop,
        "country": detect_country(all_text),
        "topic": classify_topic(all_text),
        "title": display_title,
        "Summary": "",
        "publisher_name": publisher,
        "publisher_domain": domain,
        "source_type": source_type,
        "source_name": source_name,
        "language": "en",
        "url": link,
        "google_news_url": link if source_type == "Google News RSS" else "",
        "search_query": query,
        "summary_raw": summary_raw,
        "status": "ARTICLE",
    }


def collect_google_news(query: str, crop: str, max_items: int = DEFAULT_MAX_ITEMS):
    query_with_buffer = f"({query}) when:2d"
    url = "https://news.google.com/rss/search?q=" + quote_plus(query_with_buffer) + "&hl=en-US&gl=US&ceid=US:en"
    feed, request_error = _fetch_feed(url)
    entries = list(feed.entries)
    rows = [_base_row(entry, crop, query, "Google News RSS", "Google News", url) for entry in entries[:max_items]]
    error = request_error or (str(getattr(feed, "bozo_exception", "")) if getattr(feed, "bozo", False) else "")
    diagnostic = {
        "source_name": f"Google News: {crop}", "source_type": "Google News RSS",
        "source_url": url, "success": not bool(error), "articles_received": len(entries),
        "articles_relevant": len(rows), "row_limit": max_items,
        "possibly_truncated": len(entries) >= max_items, "error": error,
    }
    return rows, diagnostic


def _detect_crop(text: str, crops: dict) -> str:
    aliases = {
        "Mango": ["mango"], "Cashew": ["cashew"], "Rice": ["rice", "paddy"],
        "Vegetables": ["vegetable", "vegetables", "fresh produce"],
    }
    lowered = text.lower()
    for crop in crops:
        if any(alias in lowered for alias in aliases.get(crop, [crop.lower()])):
            return crop
    return ""


def collect_curated_rss(source: dict, crops: dict, max_items: int = DEFAULT_MAX_ITEMS):
    feed, request_error = _fetch_feed(source["url"])
    entries = list(feed.entries)
    rows = []
    for entry in entries[:max_items]:
        text = clean_text(f"{entry.get('title', '')} {entry.get('summary', '')}")
        crop = _detect_crop(text, crops)
        if crop:
            rows.append(_base_row(entry, crop, source.get("name", ""), "Curated RSS", source.get("name", ""), source["url"]))
    error = request_error or (str(getattr(feed, "bozo_exception", "")) if getattr(feed, "bozo", False) else "")
    diagnostic = {
        "source_name": source.get("name", ""), "source_type": "Curated RSS",
        "source_url": source["url"], "success": not bool(error),
        "articles_received": len(entries), "articles_relevant": len(rows),
        "row_limit": max_items, "possibly_truncated": len(entries) >= max_items,
        "error": error,
    }
    return rows, diagnostic


def collect_all_news_with_diagnostics() -> tuple[pd.DataFrame, pd.DataFrame]:
    config = _load_json(KEYWORDS_FILE)
    sources = _load_json(SOURCES_FILE)
    crops = config.get("crops", {})
    rows: list[dict] = []
    diagnostics: list[dict] = []
    for crop, queries in crops.items():
        for query in queries:
            print(f"Collecting Google News: {query}")
            collected, diagnostic = collect_google_news(query, crop)
            rows.extend(collected)
            diagnostics.append(diagnostic)
            time.sleep(0.25)
    for source in sources.get("rss_sources", []):
        print(f"Collecting curated RSS: {source.get('name')}")
        collected, diagnostic = collect_curated_rss(source, crops)
        rows.extend(collected)
        diagnostics.append(diagnostic)
        time.sleep(0.25)
    return pd.DataFrame(rows), pd.DataFrame(diagnostics)


def collect_all_news() -> pd.DataFrame:
    return collect_all_news_with_diagnostics()[0]
