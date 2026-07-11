from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.drive.drive import (
    copy_drive_file,
    download_file_by_id,
    find_file_by_name,
    get_file_metadata,
    resolve_subfolder,
    upload_file,
)
from src.utils.dates import (
    CAMBODIA_TZ,
    add_published_columns,
    remove_timezone_columns,
)
from src.utils.duplicate import deduplicate_articles


MASTER_FILENAME = "PEARL_master_news.csv"

REQUIRED_BUSINESS_COLUMNS = {
    "title",
    "url",
}

DEFAULT_MASTER_COLUMNS = {
    "date_collected": "",
    "run_time_cambodia": "",
    "published_date": "",
    "crop": "",
    "country": "",
    "topic": "",
    "title": "",
    "Summary": "",
    "publisher_name": "",
    "publisher_domain": "",
    "source_type": "",
    "source_name": "",
    "language": "en",
    "url": "",
    "canonical_url": "",
    "google_news_url": "",
    "search_query": "",
    "article_id": "",
    "status": "ARTICLE",
}


@dataclass
class MasterState:
    dataframe: pd.DataFrame
    file_id: str
    drive_name: str
    local_path: Path
    record_count: int
    backup_name: str | None = None


def _configured_master_id() -> str:
    return os.getenv(
        "GOOGLE_MASTER_FILE_ID",
        "",
    ).strip()


def _safe_text_series(
    df: pd.DataFrame,
    column: str,
    default: str = "",
) -> pd.Series:
    if column not in df.columns:
        return pd.Series(
            default,
            index=df.index,
            dtype="object",
        )

    return (
        df[column]
        .fillna(default)
        .astype(str)
        .replace(
            {
                "nan": default,
                "NaN": default,
                "NaT": default,
                "None": default,
            }
        )
        .str.strip()
    )


def normalize_master_schema(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalize historical, daily, weekly and monthly records to one schema.

    The function deliberately preserves supplementary columns used by the
    collector while guaranteeing the business columns required by the master.
    """
    if df is None:
        df = pd.DataFrame()

    out = df.copy()

    rename_map = {
        "Date Collected": "date_collected",
        "date collected": "date_collected",
        "run_time": "run_time_cambodia",
        "Run Time Cambodia": "run_time_cambodia",
        "Published Date": "published_date",
        "Crop": "crop",
        "Country": "country",
        "Topic": "topic",
        "Title": "title",
        "summary": "Summary",
        "Publisher": "publisher_name",
        "Publisher Name": "publisher_name",
        "Publisher Domain": "publisher_domain",
        "source": "source_name",
        "Source Type": "source_type",
        "Source Name": "source_name",
        "Language": "language",
        "URL": "url",
        "Canonical URL": "canonical_url",
        "Google News URL": "google_news_url",
        "Search Query": "search_query",
        "Article ID": "article_id",
        "Status": "status",
        "Master Status": "master_status",
    }

    applicable_renames = {
        source: target
        for source, target in rename_map.items()
        if source in out.columns and source != target
    }

    out = out.rename(columns=applicable_renames)

    # A rename may create duplicate column names when historical and current
    # names both occur. Merge duplicates from left to right.
    if out.columns.duplicated().any():
        merged_columns: dict[str, pd.Series] = {}

        for column in dict.fromkeys(out.columns):
            matching = out.loc[
                :,
                out.columns == column,
            ]

            if matching.shape[1] == 1:
                merged_columns[column] = matching.iloc[:, 0]
                continue

            combined = matching.iloc[:, 0]

            for position in range(1, matching.shape[1]):
                candidate = matching.iloc[:, position]

                empty = (
                    combined.isna()
                    | combined.astype(str).str.strip().isin(
                        ["", "nan", "NaT", "None"]
                    )
                )

                combined = combined.where(
                    ~empty,
                    candidate,
                )

            merged_columns[column] = combined

        out = pd.DataFrame(
            merged_columns,
            index=out.index,
        )

    for column, default in DEFAULT_MASTER_COLUMNS.items():
        if column not in out.columns:
            out[column] = default

    if "Summary" not in out.columns:
        out["Summary"] = ""

    out["publisher_name"] = _safe_text_series(
        out,
        "publisher_name",
    )

    out["source_name"] = _safe_text_series(
        out,
        "source_name",
    )

    missing_publisher = out["publisher_name"].eq("")
    out.loc[missing_publisher, "publisher_name"] = (
        out.loc[missing_publisher, "source_name"]
    )

    missing_source = out["source_name"].eq("")
    out.loc[missing_source, "source_name"] = (
        out.loc[missing_source, "publisher_name"]
    )

    text_columns = [
        "date_collected",
        "run_time_cambodia",
        "published_date",
        "crop",
        "country",
        "topic",
        "title",
        "Summary",
        "publisher_name",
        "publisher_domain",
        "source_type",
        "source_name",
        "language",
        "url",
        "canonical_url",
        "google_news_url",
        "search_query",
        "article_id",
        "status",
    ]

    for column in text_columns:
        out[column] = _safe_text_series(
            out,
            column,
            DEFAULT_MASTER_COLUMNS.get(column, ""),
        )

    out.loc[
        out["source_type"].eq(""),
        "source_type",
    ] = "Historical Import"

    out.loc[
        out["language"].eq(""),
        "language",
    ] = "en"

    out.loc[
        out["status"].eq(""),
        "status",
    ] = "ARTICLE"

    return out


def _article_rows(
    df: pd.DataFrame,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    statuses = _safe_text_series(
        df,
        "status",
        "ARTICLE",
    ).str.upper()

    return df.loc[
        ~statuses.str.startswith("NO_")
    ].copy()


def validate_master(
    df: pd.DataFrame,
    *,
    allow_empty: bool = False,
) -> None:
    if df is None:
        raise RuntimeError(
            "Master validation failed: dataframe is None."
        )

    if df.empty:
        if allow_empty:
            return

        raise RuntimeError(
            "Master validation failed: master contains zero records."
        )

    missing = REQUIRED_BUSINESS_COLUMNS - set(df.columns)

    if missing:
        raise RuntimeError(
            "Master validation failed: missing required columns "
            f"{sorted(missing)}"
        )

    article_rows = _article_rows(df)

    if article_rows.empty and not allow_empty:
        raise RuntimeError(
            "Master validation failed: no article rows were found."
        )

    usable = article_rows.loc[
        article_rows["title"].astype(str).str.strip().ne("")
        | article_rows["url"].astype(str).str.strip().ne("")
    ]

    if usable.empty and not allow_empty:
        raise RuntimeError(
            "Master validation failed: all article rows have both "
            "an empty title and an empty URL."
        )


def load_master_safely(
    local_path: str | Path,
    *,
    create_backup: bool = True,
) -> MasterState:
    local_path = Path(local_path)
    local_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    configured_id = _configured_master_id()

    if configured_id:
        metadata = get_file_metadata(configured_id)
    else:
        master_folder = resolve_subfolder("Master")

        metadata = find_file_by_name(
            MASTER_FILENAME,
            require_unique=True,
            folder_id=master_folder,
        )

        if not metadata:
            raise RuntimeError(
                f"Production master {MASTER_FILENAME!r} was not "
                "found in the Drive/Master folder."
            )

    download_file_by_id(
        metadata["id"],
        str(local_path),
    )

    if (
        not local_path.exists()
        or local_path.stat().st_size == 0
    ):
        raise RuntimeError(
            "Master download produced an empty or missing local file."
        )

    try:
        downloaded = pd.read_csv(
            local_path,
            encoding="utf-8-sig",
            low_memory=False,
        )
    except UnicodeDecodeError:
        downloaded = pd.read_csv(
            local_path,
            encoding="utf-8",
            low_memory=False,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Master CSV could not be read: {exc}"
        ) from exc

    dataframe = normalize_master_schema(downloaded)
    validate_master(dataframe)

    backup_name: str | None = None

    if create_backup:
        stamp = datetime.now(
            CAMBODIA_TZ
        ).strftime("%Y-%m-%d_%H%M%S")

        backup_name = (
            f"PEARL_master_news_backup_{stamp}.csv"
        )

        backup_folder = resolve_subfolder(
            "Master_Backups"
        )

        copy_drive_file(
            metadata["id"],
            backup_name,
            folder_id=backup_folder,
        )

    return MasterState(
        dataframe=dataframe,
        file_id=metadata["id"],
        drive_name=metadata["name"],
        local_path=local_path,
        record_count=len(dataframe),
        backup_name=backup_name,
    )


def combine_and_validate_master(
    old_master: pd.DataFrame,
    new_articles: pd.DataFrame,
    *,
    maximum_allowed_drop: int = 0,
) -> pd.DataFrame:
    """
    Combine historical and newly collected records through one normalized,
    deterministic master pipeline.
    """
    old = normalize_master_schema(old_master)
    new = normalize_master_schema(new_articles)

    validate_master(old)

    old_unique = deduplicate_articles(old)

    if new.empty:
        combined = old_unique
    else:
        combined_input = pd.concat(
            [new, old],
            ignore_index=True,
            sort=False,
        )

        combined_input = add_published_columns(
            combined_input
        )

        combined = deduplicate_articles(
            combined_input
        )

    combined = normalize_master_schema(combined)
    validate_master(combined)

    old_count = len(old_unique)
    proposed_count = len(combined)

    if proposed_count < old_count - maximum_allowed_drop:
        raise RuntimeError(
            "Master safety check failed: "
            f"old master had {old_count} unique records, but the "
            f"proposed master has only {proposed_count}."
        )

    return combined.reset_index(drop=True)


def save_master_transaction(
    state: MasterState,
    combined: pd.DataFrame,
    *,
    local_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Validate, serialize, reread and upload the master as one transaction.
    """
    target = Path(
        local_path or state.local_path
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = target.with_suffix(
        ".validated.tmp.csv"
    )

    normalized = normalize_master_schema(combined)
    validate_master(normalized)

    clean = remove_timezone_columns(
        normalized.copy()
    )

    clean.to_csv(
        temporary,
        index=False,
        encoding="utf-8-sig",
    )

    if (
        not temporary.exists()
        or temporary.stat().st_size == 0
    ):
        raise RuntimeError(
            "Master transaction failed: temporary CSV is empty."
        )

    try:
        verification = pd.read_csv(
            temporary,
            encoding="utf-8-sig",
            low_memory=False,
        )
    except Exception as exc:
        temporary.unlink(missing_ok=True)

        raise RuntimeError(
            f"Master transaction reread failed: {exc}"
        ) from exc

    verification = normalize_master_schema(
        verification
    )

    validate_master(verification)

    if len(verification) != len(normalized):
        temporary.unlink(missing_ok=True)

        raise RuntimeError(
            "Master transaction verification failed: "
            f"{len(normalized)} rows were written, but "
            f"{len(verification)} rows were read back."
        )

    shutil.move(
        str(temporary),
        str(target),
    )

    return upload_file(
        str(target),
        MASTER_FILENAME,
        replace=True,
        file_id=state.file_id,
    )


def validate_master_file(
    path: str | Path,
) -> dict[str, int]:
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Master file does not exist: {path}"
        )

    dataframe = pd.read_csv(
        path,
        encoding="utf-8-sig",
        low_memory=False,
    )

    dataframe = normalize_master_schema(
        dataframe
    )

    validate_master(dataframe)

    enriched = add_published_columns(
        dataframe.copy()
    )

    unique = deduplicate_articles(
        enriched.copy()
    )

    invalid_dates = 0

    if "published_dt_kh" in enriched.columns:
        invalid_dates = int(
            enriched["published_dt_kh"]
            .isna()
            .sum()
        )

    return {
        "records": len(dataframe),
        "unique_records": len(unique),
        "duplicate_records": (
            len(dataframe) - len(unique)
        ),
        "invalid_publication_dates": invalid_dates,
    }
