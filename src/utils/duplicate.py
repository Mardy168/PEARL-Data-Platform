from __future__ import annotations

import hashlib
import html
import re
from typing import Final
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd


TRACKING_KEYS: Final[set[str]] = {
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

TRACKING_PREFIXES: Final[tuple[str, ...]] = (
    "utm_",
    "ga_",
)

DATE_COLUMNS: Final[tuple[str, ...]] = (
    "published_dt_kh",
    "published_dt_utc",
    "published_dt",
    "published_date",
    "Published Date",
)

TEMPORARY_SORT_COLUMN: Final[str] = "_dedup_sort_datetime"


def _safe_string(value: object) -> str:
    """Convert a value to text without turning NaN/NaT into meaningful text."""
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip()


def clean_text(text: object) -> str:
    """Remove HTML markup, decode entities and normalize whitespace."""
    value = html.unescape(_safe_string(text))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[\u200b-\u200d\ufeff]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(title: object) -> str:
    """
    Normalize English and Khmer titles for deterministic duplicate matching.

    Khmer Unicode characters are retained.
    """
    value = clean_text(title).lower()
    value = re.sub(r"[^a-z0-9\u1780-\u17ff\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(url: object) -> str:
    """
    Normalize an article URL.

    Tracking parameters and fragments are removed while meaningful query
    parameters are retained.
    """
    raw = _safe_string(url)
    if not raw:
        return ""

    try:
        parsed = urlparse(raw)

        # A URL without a scheme may otherwise be interpreted as a path.
        if not parsed.netloc and parsed.path:
            parsed = urlparse(f"https://{raw}")

        scheme = (parsed.scheme or "https").lower()
        host = parsed.netloc.lower()

        if host.startswith("www."):
            host = host[4:]

        if not host:
            return raw.split("#", 1)[0].strip()

        port = parsed.port
        if port is not None:
            default_port = (
                scheme == "http" and port == 80
            ) or (
                scheme == "https" and port == 443
            )
            if not default_port:
                host = f"{parsed.hostname}:{port}"
            else:
                host = parsed.hostname or host

        cleaned_parameters: list[tuple[str, str]] = []

        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        ):
            lower_key = key.lower()

            if lower_key in TRACKING_KEYS:
                continue

            if any(
                lower_key.startswith(prefix)
                for prefix in TRACKING_PREFIXES
            ):
                continue

            cleaned_parameters.append((key, value))

        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        if path != "/":
            path = path.rstrip("/")

        query = urlencode(sorted(cleaned_parameters))

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


def get_domain(url: object) -> str:
    """Extract a normalized publisher domain from a URL."""
    normalized = normalize_url(url)

    if not normalized:
        return ""

    try:
        host = urlparse(normalized).netloc.lower()

        if host.startswith("www."):
            host = host[4:]

        return host

    except (TypeError, ValueError):
        return ""


def make_hash(value: object) -> str:
    """Create a deterministic SHA-256 identifier."""
    return hashlib.sha256(
        _safe_string(value).encode("utf-8")
    ).hexdigest()


def normalize_duplicate_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create one UTC datetime column used only for deterministic sorting.

    This prevents Pandas from comparing strings directly with Timestamp
    objects. Invalid or missing values become NaT.
    """
    out = df.copy()

    candidate_series: list[pd.Series] = []

    for column in DATE_COLUMNS:
        if column not in out.columns:
            continue

        parsed = pd.to_datetime(
            out[column],
            errors="coerce",
            utc=True,
            format="mixed",
        )

        candidate_series.append(parsed)

    if not candidate_series:
        out[TEMPORARY_SORT_COLUMN] = pd.Series(
            pd.NaT,
            index=out.index,
            dtype="datetime64[ns, UTC]",
        )
        return out

    combined = candidate_series[0]

    for candidate in candidate_series[1:]:
        combined = combined.fillna(candidate)

    out[TEMPORARY_SORT_COLUMN] = combined
    return out


def add_duplicate_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Add normalized URL, title and stable duplicate identifiers."""
    out = df.copy()

    defaults = {
        "title": "",
        "url": "",
        "publisher_domain": "",
    }

    for column, default in defaults.items():
        if column not in out.columns:
            out[column] = default

    out["title"] = out["title"].apply(_safe_string)
    out["url"] = out["url"].apply(_safe_string)
    out["publisher_domain"] = (
        out["publisher_domain"]
        .apply(_safe_string)
        .str.lower()
        .str.strip()
    )

    out["clean_title"] = out["title"].apply(normalize_title)
    out["canonical_url"] = out["url"].apply(normalize_url)

    missing_domain = out["publisher_domain"].eq("")

    out.loc[missing_domain, "publisher_domain"] = (
        out.loc[missing_domain, "canonical_url"]
        .apply(get_domain)
    )

    out["url_id"] = out["canonical_url"].apply(make_hash)

    same_site_identity = (
        out["publisher_domain"]
        + "|"
        + out["clean_title"]
    )

    out["same_site_title_id"] = same_site_identity.apply(make_hash)

    # Canonical URL is preferred, while the publisher/title identity provides
    # a deterministic fallback for feeds with rewritten or missing URLs.
    article_identity = (
        out["url_id"]
        + "|"
        + out["same_site_title_id"]
    )

    out["article_id"] = article_identity.apply(make_hash)

    return out


def deduplicate_articles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplicate article records deterministically.

    Rules:
    1. Newer publication records are preferred.
    2. Exact canonical URLs are retained once.
    3. The same normalized title from the same publisher is retained once.
    4. Similar events from different publishers remain separate.
    """
    if df is None:
        return add_duplicate_keys(pd.DataFrame())

    if df.empty:
        return add_duplicate_keys(df).reset_index(drop=True)

    out = add_duplicate_keys(df)
    out = normalize_duplicate_dates(out)

    # Stable sorting preserves original order when publication times match.
    out["_dedup_original_order"] = range(len(out))

    out = out.sort_values(
        by=[
            TEMPORARY_SORT_COLUMN,
            "_dedup_original_order",
        ],
        ascending=[
            False,
            True,
        ],
        na_position="last",
        kind="mergesort",
    )

    has_url = out["canonical_url"].str.strip().ne("")

    with_url = (
        out.loc[has_url]
        .drop_duplicates(
            subset=["url_id"],
            keep="first",
        )
    )

    without_url = out.loc[~has_url]

    out = pd.concat(
        [with_url, without_url],
        ignore_index=True,
        sort=False,
    )

    # Do not use an empty title as a duplicate key. Empty titles would
    # otherwise collapse unrelated articles from the same publisher.
    has_title = out["clean_title"].str.strip().ne("")

    with_title = (
        out.loc[has_title]
        .drop_duplicates(
            subset=["same_site_title_id"],
            keep="first",
        )
    )

    without_title = out.loc[~has_title]

    out = pd.concat(
        [with_title, without_title],
        ignore_index=True,
        sort=False,
    )

    out = out.sort_values(
        by=[
            TEMPORARY_SORT_COLUMN,
            "_dedup_original_order",
        ],
        ascending=[
            False,
            True,
        ],
        na_position="last",
        kind="mergesort",
    )

    out = out.drop(
        columns=[
            TEMPORARY_SORT_COLUMN,
            "_dedup_original_order",
        ],
        errors="ignore",
    )

    return out.reset_index(drop=True)


def exclude_existing(
    df: pd.DataFrame,
    master: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return only records that do not already occur in the normalized master.
    """
    if df is None or df.empty:
        return add_duplicate_keys(
            pd.DataFrame() if df is None else df
        ).reset_index(drop=True)

    new = deduplicate_articles(df)

    if master is None or master.empty:
        return new.reset_index(drop=True)

    old = deduplicate_articles(master)

    old_urls = set(
        old.loc[
            old["canonical_url"].str.strip().ne(""),
            "url_id",
        ].astype(str)
    )

    old_titles = set(
        old.loc[
            old["clean_title"].str.strip().ne(""),
            "same_site_title_id",
        ].astype(str)
    )

    has_url = new["canonical_url"].str.strip().ne("")
    has_title = new["clean_title"].str.strip().ne("")

    url_is_new = ~new["url_id"].astype(str).isin(old_urls)
    title_is_new = ~new["same_site_title_id"].astype(str).isin(
        old_titles
    )

    keep = pd.Series(True, index=new.index)

    keep.loc[has_url] &= url_is_new.loc[has_url]
    keep.loc[has_title] &= title_is_new.loc[has_title]

    return new.loc[keep].reset_index(drop=True)
