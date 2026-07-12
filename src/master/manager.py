from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.utils.dates import CAMBODIA_TZ, add_published_columns, remove_timezone_columns
from src.utils.duplicate import deduplicate_articles

MASTER_FILENAME = "PEARL_master_news.csv"
REQUIRED_BUSINESS_COLUMNS = {"title", "url"}

DEFAULT_COLUMNS = {
    "date_collected": "", "run_time_cambodia": "", "published_date": "",
    "crop": "", "country": "", "topic": "", "title": "", "Summary": "",
    "publisher_name": "", "publisher_domain": "", "source_type": "",
    "source_name": "", "language": "en", "url": "", "google_news_url": "",
    "search_query": "", "status": "ARTICLE", "master_status": "",
}


@dataclass
class MasterState:
    dataframe: pd.DataFrame
    local_path: Path
    record_count: int
    backup_name: str | None = None


def _clean_series(df: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="object")
    return (
        df[column].fillna(default).astype(str)
        .replace({"nan": default, "NaN": default, "NaT": default, "None": default})
        .str.strip()
    )


def normalize_master_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame() if df is None else df.copy()
    rename_map = {
        "Date Collected": "date_collected", "Run Time Cambodia": "run_time_cambodia",
        "run_time": "run_time_cambodia", "Published Date": "published_date",
        "Crop": "crop", "Country": "country", "Topic": "topic", "Title": "title",
        "summary": "Summary", "Publisher": "publisher_name",
        "Publisher Domain": "publisher_domain", "source": "source_name",
        "Source Type": "source_type", "Source Name": "source_name",
        "Language": "language", "URL": "url", "Google News URL": "google_news_url",
        "Search Query": "search_query", "Status": "status", "Master Status": "master_status",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns and k != v})
    if out.columns.duplicated().any():
        merged: dict[str, pd.Series] = {}
        for column in dict.fromkeys(out.columns):
            matching = out.loc[:, out.columns == column]
            series = matching.iloc[:, 0]
            for pos in range(1, matching.shape[1]):
                candidate = matching.iloc[:, pos]
                empty = series.isna() | series.astype(str).str.strip().isin(["", "nan", "NaT", "None"])
                series = series.where(~empty, candidate)
            merged[column] = series
        out = pd.DataFrame(merged, index=out.index)
    for column, default in DEFAULT_COLUMNS.items():
        if column not in out.columns:
            out[column] = default
    if "publisher_name" not in out.columns:
        out["publisher_name"] = out.get("source_name", "")
    if "source_name" not in out.columns:
        out["source_name"] = out.get("publisher_name", "")
    for column, default in DEFAULT_COLUMNS.items():
        out[column] = _clean_series(out, column, default)
    missing_publisher = out["publisher_name"].eq("")
    out.loc[missing_publisher, "publisher_name"] = out.loc[missing_publisher, "source_name"]
    missing_source = out["source_name"].eq("")
    out.loc[missing_source, "source_name"] = out.loc[missing_source, "publisher_name"]
    out.loc[out["status"].eq(""), "status"] = "ARTICLE"
    return out


def validate_master(df: pd.DataFrame, *, allow_empty: bool = False) -> None:
    if df.empty:
        if allow_empty:
            return
        raise RuntimeError("Master validation failed: master contains zero records.")
    missing = REQUIRED_BUSINESS_COLUMNS - set(df.columns)
    if missing:
        raise RuntimeError(f"Master validation failed: missing columns {sorted(missing)}")
    articles = df.loc[~df["status"].astype(str).str.startswith("NO_")]
    if articles.empty and not allow_empty:
        raise RuntimeError("Master validation failed: no article rows were found.")


def load_master_safely(local_path: str | Path, *, create_backup: bool = True) -> MasterState:
    path = Path(local_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        empty = normalize_master_schema(pd.DataFrame())
        return MasterState(empty, path, 0, None)
    if path.stat().st_size == 0:
        raise RuntimeError(f"Master file is empty: {path}")
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        frame = pd.read_csv(path, encoding="utf-8", low_memory=False)
    frame = normalize_master_schema(frame)
    if not frame.empty:
        validate_master(frame)
    backup_name = None
    if create_backup and not frame.empty:
        backup_dir = path.parent.parent / "master_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d_%H%M%S")
        backup_path = backup_dir / f"PEARL_master_news_backup_{stamp}.csv"
        shutil.copy2(path, backup_path)
        backup_name = backup_path.name
    return MasterState(frame, path, len(frame), backup_name)


def combine_and_validate_master(old_master: pd.DataFrame, new_articles: pd.DataFrame) -> pd.DataFrame:
    old = normalize_master_schema(old_master)
    new = normalize_master_schema(new_articles)
    combined = deduplicate_articles(pd.concat([new, old], ignore_index=True, sort=False))
    combined = normalize_master_schema(combined)
    if not combined.empty:
        validate_master(combined)
    old_unique = len(deduplicate_articles(old)) if not old.empty else 0
    if len(combined) < old_unique:
        raise RuntimeError(f"Master safety check failed: {old_unique} old unique rows versus {len(combined)} proposed.")
    return combined.reset_index(drop=True)


def save_master_transaction(state: MasterState, combined: pd.DataFrame, *, local_path: str | Path | None = None) -> Path:
    target = Path(local_path or state.local_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_master_schema(combined)
    if not normalized.empty:
        validate_master(normalized)
    temp = target.with_suffix(".validated.tmp.csv")
    remove_timezone_columns(normalized).to_csv(temp, index=False, encoding="utf-8-sig")
    verification = normalize_master_schema(pd.read_csv(temp, encoding="utf-8-sig", low_memory=False))
    if len(verification) != len(normalized):
        temp.unlink(missing_ok=True)
        raise RuntimeError("Master transaction verification failed: row count changed after write.")
    shutil.move(str(temp), str(target))
    return target


def normalized_master_for_reporting(path: str | Path) -> pd.DataFrame:
    state = load_master_safely(path, create_backup=False)
    frame = add_published_columns(state.dataframe)
    frame = deduplicate_articles(frame)
    if "status" in frame.columns:
        frame = frame.loc[frame["status"].astype(str).eq("ARTICLE")]
    return frame.reset_index(drop=True)


def validate_master_file(path: str | Path) -> dict[str, int]:
    state = load_master_safely(path, create_backup=False)
    enriched = add_published_columns(state.dataframe.copy())
    unique = deduplicate_articles(enriched)
    return {
        "records": len(state.dataframe),
        "unique_records": len(unique),
        "duplicate_records": len(state.dataframe) - len(unique),
        "invalid_publication_dates": int(enriched["published_dt_kh"].isna().sum()),
    }
