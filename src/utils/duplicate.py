from __future__ import annotations

import hashlib, html, re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import pandas as pd

TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"}
TRACKING_PREFIXES = ("utm_",)


def clean_text(text: object) -> str:
    value = html.unescape(str(text or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(title: object) -> str:
    value = clean_text(title).lower()
    value = re.sub(r"[^a-z0-9\u1780-\u17ff\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(url: object) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        p = urlparse(raw)
        scheme = (p.scheme or "https").lower()
        host = p.netloc.lower().replace("www.", "")
        params=[]
        for k,v in parse_qsl(p.query, keep_blank_values=True):
            lk=k.lower()
            if lk in TRACKING_KEYS or lk.startswith(TRACKING_PREFIXES):
                continue
            params.append((k,v))
        path = re.sub(r"/{2,}", "/", p.path).rstrip("/") or "/"
        return urlunparse((scheme, host, path, "", urlencode(sorted(params)), ""))
    except Exception:
        return raw.split("#",1)[0]


def get_domain(url: object) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def make_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def add_duplicate_keys(df: pd.DataFrame) -> pd.DataFrame:
    out=df.copy()
    for col in ("title","url","publisher_domain"):
        if col not in out.columns: out[col]=""
    out["clean_title"] = out["title"].apply(normalize_title)
    out["canonical_url"] = out["url"].apply(normalize_url)
    missing = out["publisher_domain"].fillna("").astype(str).str.strip().eq("")
    out.loc[missing,"publisher_domain"] = out.loc[missing,"canonical_url"].apply(get_domain)
    out["url_id"] = out["canonical_url"].apply(make_hash)
    out["same_site_title_id"] = (out["publisher_domain"].astype(str).str.lower().str.strip()+"|"+out["clean_title"]).apply(make_hash)
    # Stable ID prioritizes canonical URL, while retaining publisher/title identity.
    out["article_id"] = (out["url_id"]+"|"+out["same_site_title_id"]).apply(make_hash)
    return out


def deduplicate_articles(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return add_duplicate_keys(df)
    out=add_duplicate_keys(df)
    if "published_dt_kh" in out.columns:
        out=out.sort_values("published_dt_kh", ascending=False, na_position="last")
    # Preserve same event from different publishers.
    nonempty_url=out["canonical_url"].astype(str).str.strip().ne("")
    with_url=out[nonempty_url].drop_duplicates("url_id", keep="first")
    without_url=out[~nonempty_url]
    out=pd.concat([with_url,without_url], ignore_index=True)
    out=out.drop_duplicates("same_site_title_id", keep="first")
    return out.reset_index(drop=True)


def exclude_existing(df: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    new=add_duplicate_keys(df)
    if master.empty: return new.reset_index(drop=True)
    old=add_duplicate_keys(master)
    old_urls=set(old.loc[old["canonical_url"].astype(str).str.strip().ne(""),"url_id"].astype(str))
    old_titles=set(old["same_site_title_id"].astype(str))
    mask=(~new["same_site_title_id"].astype(str).isin(old_titles))
    has_url=new["canonical_url"].astype(str).str.strip().ne("")
    mask &= (~has_url) | (~new["url_id"].astype(str).isin(old_urls))
    return new[mask].reset_index(drop=True)
