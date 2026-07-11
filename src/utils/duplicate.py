from __future__ import annotations

import hashlib
import html
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd


TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "dclid",
    "gbraid",
    "wbraid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
}

TRACKING_PREFIXES = ("utm_", "ga_")

DATE_COLUMNS = (
    "published_dt_kh",
    "published_dt_utc",
    "published_dt",
    "published_date",
    "Published Date",
)

SORT_DATE_COLUMN = "_dedup_sort_date"
ORIGINAL_ORDER_COLUMN = "_dedup_original_order"


def safe_text(value: object) -> str:
    """Convert a scalar value to clean text without preserving NaN/NaT."""
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip()


def clean_text(value: object) -> str:
    """Remove HTML markup and normalize whitespace."""
    text = html.unescape(safe_text(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\u200b-\u200d\ufeff]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(value: object) -> str:
    """Normalize English and Khmer text for duplicate comparison."""
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9\u1780-\u17ff\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(value: object) -> str:
    """Remove fragments and common tracking parameters from a URL."""
    raw = safe_text(value)
    if not raw:
        return ""

    try:
        parsed = urlparse(raw)

        if not parsed.scheme and not parsed.netloc:
            parsed = urlparse(f"https://{raw}")

        scheme = (parsed.scheme or "https").lower()
        host = parsed.netloc.lower()

        if host.startswith("www."):
            host = host[4:]

        if not host:
            return raw.split("#", 1)[0].strip()

        parameters: list[tuple[str, str]] = []

        for key, item_value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        ):
            normalized_key = key.lower()

            if normalized_key in TRACKING_KEYS:
                continue

            if normalized_key.startswith(TRACKING_PREFIXES):
                continue

            parameters.append((key, item_value))

        path = re.sub(r"/{2,}", "/", parsed.path or "/")

        if path != "/":
            path = path.rstrip("/")

        query = urlencode(sorted(parameters))

        return urlunparse(
            (
                scheme,
                host,
                path,
                "",
                query,
                "",
            )
        )

    except (TypeError, ValueError):
        return raw.split("#", 1)[0].strip()


def extract_domain(value: object) -> str:
    """Return the normalized hostname from a URL."""
    normalized = normalize_url(value)

    if not normalized:
        return ""

    try:
        return urlparse(normalized).netloc.lower().removeprefix("www.")
    except (TypeError, ValueError):
        return ""


def make_hash(value: object) -> str:
    """Return a stable SHA-256 hash."""
    return hashlib.sha256(
        safe_text(value).encode("utf-8")
    ).hexdigest()


def add_duplicate_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Add normalized duplicate-matching fields."""
    out = df.copy()

    for column in ("title", "url", "publisher_domain"):
        if column not in out.columns:
            out[column] = ""

        out[column] = out[column].apply(safe_text)

    out["clean_title"] = out["title"].apply(normalize_title)
    out["canonical_url"] = out["url"].apply(normalize_url)

    missing_domain = out["publisher_domain"].eq("")

    out.loc[missing_domain, "publisher_domain"] = (
        out.loc[missing_domain, "canonical_url"]
        .apply(extract_domain)
    )

    out["publisher_domain"] = (
        out["publisher_domain"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    out["url_id"] = out["canonical_url"].apply(make_hash)

    out["same_site_title_id"] = (
        out["publisher_domain"]
        + "|"
        + out["clean_title"]
    ).apply(make_hash)

    out["article_id"] = (
        out["url_id"]
        + "|"
        + out["same_site_title_id"]
    ).apply(make_hash)

    return out


def add_normalized_sort_date(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build one UTC datetime series for sorting.

    All strings, naive timestamps and timezone-aware timestamps are converted
    to datetime64[ns, UTC]. Invalid values become NaT.
    """
    out = df.copy()

    combined = pd.Series(
        pd.NaT,
        index=out.index,
        dtype="datetime64[ns, UTC]",
    )

    for column in DATE_COLUMNS:
        if column not in out.columns:
            continue

        parsed = pd.to_datetime(
            out[column],
            errors="coerce",
            utc=True,
            format="mixed",
        )

        combined = combined.fillna(parsed)

    out[SORT_DATE_COLUMN] = combined
    return out


def deduplicate_articles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplicate articles without comparing strings to Timestamp objects.

    Preference order:
    1. Newest valid publication time.
    2. Original dataframe order.
    3. One record per canonical URL.
    4. One record per normalized publisher-and-title combination.
    """
    if df is None:
        return add_duplicate_keys(pd.DataFrame())

    if df.empty:
        return add_duplicate_keys(df).reset_index(drop=True)

    out = add_duplicate_keys(df)
    out = add_normalized_sort_date(out)
    out[ORIGINAL_ORDER_COLUMN] = range(len(out))

    out = out.sort_values(
        by=[SORT_DATE_COLUMN, ORIGINAL_ORDER_COLUMN],
        ascending=[False, True],
        na_position="last",
        kind="mergesort",
    )

    has_url = out["canonical_url"].ne("")

    records_with_url = out.loc[has_url].drop_duplicates(
        subset=["url_id"],
        keep="first",
    )

    records_without_url = out.loc[~has_url]

    out = pd.concat(
        [records_with_url, records_without_url],
        ignore_index=True,
        sort=False,
    )

    has_title = out["clean_title"].ne("")

    records_with_title = out.loc[has_title].drop_duplicates(
        subset=["same_site_title_id"],
        keep="first",
    )

    records_without_title = out.loc[~has_title]

    out = pd.concat(
        [records_with_title, records_without_title],
        ignore_index=True,
        sort=False,
    )

    out = out.sort_values(
        by=[SORT_DATE_COLUMN, ORIGINAL_ORDER_COLUMN],
        ascending=[False, True],
        na_position="last",
        kind="mergesort",
    )

    out = out.drop(
        columns=[SORT_DATE_COLUMN, ORIGINAL_ORDER_COLUMN],
        errors="ignore",
    )

    return out.reset_index(drop=True)


def exclude_existing(
    df: pd.DataFrame,
    master: pd.DataFrame,
) -> pd.DataFrame:
    """Return records not already represented in the master dataset."""
    if df is None or df.empty:
        source = pd.DataFrame() if df is None else df
        return add_duplicate_keys(source).reset_index(drop=True)

    new_records = deduplicate_articles(df)

    if master is None or master.empty:
        return new_records

    master_records = deduplicate_articles(master)

    existing_urls = set(
        master_records.loc[
            master_records["canonical_url"].ne(""),
            "url_id",
        ].astype(str)
    )

    existing_titles = set(
        master_records.loc[
            master_records["clean_title"].ne(""),
            "same_site_title_id",
        ].astype(str)
    )

    has_url = new_records["canonical_url"].ne("")
    has_title = new_records["clean_title"].ne("")

    url_is_new = ~new_records["url_id"].astype(str).isin(
        existing_urls
    )

    title_is_new = ~new_records[
        "same_site_title_id"
    ].astype(str).isin(existing_titles)

    keep = pd.Series(True, index=new_records.index)

    keep.loc[has_url] &= url_is_new.loc[has_url]
    keep.loc[has_title] &= title_is_new.loc[has_title]

    return new_records.loc[keep].reset_index(drop=True)
