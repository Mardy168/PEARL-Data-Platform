from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.drive.drive import (
    copy_drive_file,
    download_file_by_id,
    find_file_by_name,
    get_file_metadata,
    upload_file,
)
from src.utils.dates import CAMBODIA_TZ, add_published_columns, remove_timezone_columns
from src.utils.duplicate import deduplicate_articles

MASTER_FILENAME = "PEARL_master_news.csv"
REQUIRED_BUSINESS_COLUMNS = {"title", "url"}


@dataclass
class MasterState:
    dataframe: pd.DataFrame
    file_id: str
    drive_name: str
    local_path: Path
    record_count: int
    backup_name: str | None = None


def _configured_master_id() -> str:
    return os.getenv("GOOGLE_MASTER_FILE_ID", "").strip()


def normalize_master_schema(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    rename_map = {
        "run_time": "run_time_cambodia",
        "published_date": "published_date",
        "Published Date": "Published Date",
        "source": "source_name",
        "Publisher": "publisher_name",
        "Publisher Domain": "publisher_domain",
        "Source Type": "source_type",
        "Source Name": "source_name",
        "Date Collected": "date_collected",
        "Run Time Cambodia": "run_time_cambodia",
        "Crop": "crop",
        "Country": "country",
        "Topic": "topic",
        "Title": "title",
        "Summary": "Summary",
        "Language": "language",
        "URL": "url",
        "Canonical URL": "canonical_url",
        "Google News URL": "google_news_url",
        "Search Query": "search_query",
        "Article ID": "article_id",
        "Status": "status",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}).copy()
    if "Summary" not in df.columns and "summary" in df.columns:
        df["Summary"] = df["summary"]
    if "publisher_name" not in df.columns:
        df["publisher_name"] = df.get("source_name", df.get("source", ""))
    if "source_name" not in df.columns:
        df["source_name"] = df.get("publisher_name", "")
    if "source_type" not in df.columns:
        df["source_type"] = "Historical Import"
    if "status" not in df.columns:
        df["status"] = "ARTICLE"
    df.loc[df["status"].astype(str).str.strip().eq(""), "status"] = "ARTICLE"
    for col in ["title", "url", "crop", "country", "topic", "language", "search_query"]:
        if col not in df.columns:
            df[col] = ""
    return df


def validate_master(df: pd.DataFrame, *, allow_empty: bool = False) -> None:
    if df.empty and not allow_empty:
        raise RuntimeError("Master validation failed: the master contains zero records.")
    missing = REQUIRED_BUSINESS_COLUMNS - set(df.columns)
    if missing:
        raise RuntimeError(f"Master validation failed: missing required columns {sorted(missing)}")
    if not df.empty:
        article_rows = df[~df.get("status", "ARTICLE").astype(str).str.startswith("NO_")]
        if len(article_rows) == 0 and not allow_empty:
            raise RuntimeError("Master validation failed: no article rows were found.")


def load_master_safely(local_path: str | Path, *, create_backup: bool = True) -> MasterState:
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    configured_id = _configured_master_id()

    if configured_id:
        metadata = get_file_metadata(configured_id)
    else:
        metadata = find_file_by_name(MASTER_FILENAME, require_unique=True)
        if not metadata:
            raise RuntimeError(
                f"Production master {MASTER_FILENAME!r} was not found in Google Drive. "
                "The workflow has stopped to prevent accidental creation of an empty master."
            )

    download_file_by_id(metadata["id"], str(local_path))
    if not local_path.exists() or local_path.stat().st_size == 0:
        raise RuntimeError("Master download failed or produced an empty file. Upload cancelled.")

    try:
        df = pd.read_csv(local_path)
    except Exception as exc:
        raise RuntimeError(f"Master CSV could not be read: {exc}") from exc

    df = normalize_master_schema(df)
    validate_master(df)

    backup_name = None
    if create_backup:
        stamp = datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d_%H%M%S")
        backup_name = f"PEARL_master_news_backup_{stamp}.csv"
        copy_drive_file(metadata["id"], backup_name)

    return MasterState(
        dataframe=df,
        file_id=metadata["id"],
        drive_name=metadata["name"],
        local_path=local_path,
        record_count=len(df),
        backup_name=backup_name,
    )


def combine_and_validate_master(
    old_master: pd.DataFrame,
    new_articles: pd.DataFrame,
    *,
    maximum_allowed_drop: int = 0,
) -> pd.DataFrame:
    old_master = normalize_master_schema(old_master)
    new_articles = normalize_master_schema(new_articles)
    combined = deduplicate_articles(pd.concat([old_master, new_articles], ignore_index=True))
    validate_master(combined)

    old_count = len(deduplicate_articles(old_master))
    new_count = len(combined)
    if new_count < old_count - maximum_allowed_drop:
        raise RuntimeError(
            f"Master safety check failed: old master had {old_count} records but the proposed "
            f"master has only {new_count}. The Drive master was not updated."
        )
    return combined


def save_master_transaction(
    state: MasterState,
    combined: pd.DataFrame,
    *,
    local_path: str | Path | None = None,
) -> dict:
    target_path = Path(local_path or state.local_path)
    temporary = target_path.with_suffix(".validated.tmp.csv")
    clean = remove_timezone_columns(combined.copy())
    clean.to_csv(temporary, index=False, encoding="utf-8-sig")

    verification = normalize_master_schema(pd.read_csv(temporary))
    validate_master(verification)
    if len(verification) != len(combined):
        raise RuntimeError("Master transaction verification failed: row count changed after CSV write.")

    shutil.move(str(temporary), str(target_path))
    return upload_file(
        str(target_path),
        MASTER_FILENAME,
        replace=True,
        file_id=state.file_id,
    )


def validate_master_file(path: str | Path) -> dict[str, int]:
    path = Path(path)
    df = normalize_master_schema(pd.read_csv(path))
    validate_master(df)
    enriched = add_published_columns(df.copy())
    unique = deduplicate_articles(df.copy())
    return {
        "records": len(df),
        "unique_records": len(unique),
        "duplicate_records": len(df) - len(unique),
        "invalid_publication_dates": int(enriched["published_dt_kh"].isna().sum()),
    }
