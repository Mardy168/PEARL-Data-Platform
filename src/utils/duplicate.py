import re
import hashlib
from difflib import SequenceMatcher


def clean_text(text):
    text = re.sub(r"<.*?>", " ", str(text))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(title):
    title = clean_text(title).lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def normalize_url(url):
    url = str(url).strip()
    url = url.split("?")[0]
    url = url.split("&")[0]
    return url.strip()


def make_hash(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def title_similarity(a, b):
    return SequenceMatcher(None, str(a), str(b)).ratio()


def add_duplicate_keys(df):
    if "title" not in df.columns:
        df["title"] = ""

    if "url" not in df.columns:
        df["url"] = ""

    df["clean_title"] = df["title"].apply(normalize_title)
    df["clean_url"] = df["url"].apply(normalize_url)

    df["title_id"] = df["clean_title"].apply(make_hash)
    df["url_id"] = df["clean_url"].apply(make_hash)
    df["article_id"] = df["title_id"]

    return df


def remove_similar_titles(df, threshold=0.92):
    if df.empty:
        return df

    kept_rows = []
    kept_titles = []

    for _, row in df.iterrows():
        title = row.get("clean_title", "")

        duplicate = False

        for old_title in kept_titles:
            if title_similarity(title, old_title) >= threshold:
                duplicate = True
                break

        if not duplicate:
            kept_rows.append(row)
            kept_titles.append(title)

    return df.__class__(kept_rows)
