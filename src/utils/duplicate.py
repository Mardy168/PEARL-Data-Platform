from __future__ import annotations

import hashlib
import html
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd

TRACKING_KEYS = {
    "fbclid", "gclid", "dclid", "gbraid", "wbraid", "mc_cid", "mc_eid",
    "ref", "ref_src", "source",
}
TRACKING_PREFIXES = ("utm_", "ga_")
DATE_COLUMNS = (
    "published_dt_kh", "published_dt_utc", "published_dt",
    "published_date", "Published Date",
)
SORT_DATE_COLUMN = "_dedup_sort_date"
ORIGINAL_ORDER_COLUMN = "_dedup_original_order"


def safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def clean_text(value: object) -> str:
    text = html.unescape(safe_text(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\u200b-\u200d\ufeff]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(value: object) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9\u1780-\u17ff\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(value: object) -> str:
    raw = safe_text(value)
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        if not parsed.netloc and parsed.path:
            parsed = urlparse(f"https://{raw}")
        scheme = (parsed.scheme or "https").lower()
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if not host:
            return raw.split("#", 1)[0]
        params: list[tuple[str, str]] = []
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
            normalized_key = key.lower()
            if normalized_key in TRACKING_KEYS or normalized_key.startswith(TRACKING_PREFIXES):
                continue
            params.append((key, item_value))
        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        if path != "/":
            path = path.rstrip("/")
        return urlunparse((scheme, host, path, "", urlencode(sorted(params)), ""))
    except (TypeError, ValueError):
        return raw.split("#", 1)[0]


def get_domain(value: object) -> str:
    normalized = normalize_url(value)
    if not normalized:
        return ""
    try:
        return urlparse(normalized).netloc.lower().removeprefix("www.")
    except (TypeError, ValueError):
        return ""


def make_hash(value: object) -> str:
    return hashlib.sha256(safe_text(value).encode("utf-8")).hexdigest()


def add_duplicate_keys(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in ("title", "url", "publisher_domain"):
        if column not in out.columns:
            out[column] = ""
        out[column] = out[column].apply(safe_text)
    out["clean_title"] = out["title"].apply(normalize_title)
    out["canonical_url"] = out["url"].apply(normalize_url)
    missing_domain = out["publisher_domain"].eq("")
    out.loc[missing_domain, "publisher_domain"] = (
        out.loc[missing_domain, "canonical_url"].apply(get_domain)
    )
    out["publisher_domain"] = out["publisher_domain"].str.lower().str.strip()
    out["url_id"] = out["canonical_url"].apply(make_hash)
    out["same_site_title_id"] = (
        out["publisher_domain"] + "|" + out["clean_title"]
    ).apply(make_hash)
    out["article_id"] = (out["url_id"] + "|" + out["same_site_title_id"]).apply(make_hash)
    return out


def _add_sort_date(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    combined = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns, UTC]")
    for column in DATE_COLUMNS:
        if column in out.columns:
            parsed = pd.to_datetime(out[column], errors="coerce", utc=True, format="mixed")
            combined = combined.fillna(parsed)
    out[SORT_DATE_COLUMN] = combined
    return out


def deduplicate_articles(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return add_duplicate_keys(pd.DataFrame())
    if df.empty:
        return add_duplicate_keys(df).reset_index(drop=True)
    out = _add_sort_date(add_duplicate_keys(df))
    out[ORIGINAL_ORDER_COLUMN] = range(len(out))
    out = out.sort_values(
        [SORT_DATE_COLUMN, ORIGINAL_ORDER_COLUMN],
        ascending=[False, True], na_position="last", kind="mergesort",
    )
    has_url = out["canonical_url"].ne("")
    out = pd.concat(
        [out.loc[has_url].drop_duplicates("url_id", keep="first"), out.loc[~has_url]],
        ignore_index=True, sort=False,
    )
    has_title = out["clean_title"].ne("")
    out = pd.concat(
        [out.loc[has_title].drop_duplicates("same_site_title_id", keep="first"), out.loc[~has_title]],
        ignore_index=True, sort=False,
    )
    out = out.sort_values(
        [SORT_DATE_COLUMN, ORIGINAL_ORDER_COLUMN],
        ascending=[False, True], na_position="last", kind="mergesort",
    )
    return out.drop(columns=[SORT_DATE_COLUMN, ORIGINAL_ORDER_COLUMN], errors="ignore").reset_index(drop=True)


def exclude_existing(df: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    new = deduplicate_articles(df)
    if master is None or master.empty:
        return new
    old = deduplicate_articles(master)
    old_urls = set(old.loc[old["canonical_url"].ne(""), "url_id"].astype(str))
    old_titles = set(old.loc[old["clean_title"].ne(""), "same_site_title_id"].astype(str))
    has_url = new["canonical_url"].ne("")
    has_title = new["clean_title"].ne("")
    keep = pd.Series(True, index=new.index)
    keep.loc[has_url] &= ~new.loc[has_url, "url_id"].astype(str).isin(old_urls)
    keep.loc[has_title] &= ~new.loc[has_title, "same_site_title_id"].astype(str).isin(old_titles)
    return new.loc[keep].reset_index(drop=True)
