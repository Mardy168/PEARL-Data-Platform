from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

import pandas as pd

CAMBODIA_TZ = timezone(timedelta(hours=7), name="Asia/Phnom_Penh")
DISPLAY_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_cambodia() -> datetime:
    return datetime.now(CAMBODIA_TZ)


def ensure_cambodia_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=CAMBODIA_TZ)
    return value.astimezone(CAMBODIA_TZ)


def parse_datetime_series(values: pd.Series) -> pd.Series:
    """Parse mixed feed dates into timezone-aware UTC timestamps."""
    return pd.to_datetime(values, errors="coerce", utc=True, format="mixed")


def _first_existing_series(df: pd.DataFrame, candidates: Iterable[str]) -> pd.Series:
    for column in candidates:
        if column in df.columns:
            return df[column]
    return pd.Series("", index=df.index, dtype="object")


def add_published_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add canonical UTC and Cambodia publication timestamps.

    Assumption: feed values without an explicit timezone are interpreted by
    pandas as UTC. Most configured RSS feeds publish RFC timestamps with an
    explicit offset. Invalid values become NaT and are never placed in a
    reporting window.
    """
    out = df.copy()
    source = _first_existing_series(
        out,
        ("published_date", "Published Date", "published_dt_utc", "published_dt_kh"),
    )
    out["published_dt_utc"] = parse_datetime_series(source)
    out["published_dt_kh"] = out["published_dt_utc"].dt.tz_convert(CAMBODIA_TZ)
    out["Published Date"] = (
        out["published_dt_kh"].dt.strftime(DISPLAY_DATE_FORMAT).fillna("")
    )
    return out


def latest_daily_boundary(now: datetime, *, hour: int = 9) -> datetime:
    """Return the latest completed daily boundary in Cambodia time."""
    current = ensure_cambodia_datetime(now)
    boundary = current.replace(hour=hour, minute=0, second=0, microsecond=0)
    if current < boundary:
        boundary -= timedelta(days=1)
    return boundary


def daily_window(now: datetime, *, boundary_hour: int = 9) -> tuple[datetime, datetime]:
    end = latest_daily_boundary(now, hour=boundary_hour)
    return end - timedelta(days=1), end


def rolling_window(now: datetime, *, days: int = 0, hours: int = 0) -> tuple[datetime, datetime]:
    end = ensure_cambodia_datetime(now)
    return end - timedelta(days=days, hours=hours), end


def previous_month_window(now: datetime) -> tuple[datetime, datetime, str]:
    current = ensure_cambodia_datetime(now)
    first_current = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_day = first_current - timedelta(days=1)
    first_previous = previous_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first_previous, first_current, first_previous.strftime("%Y-%m")


def remove_timezone_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in out.columns:
        if isinstance(out[column].dtype, pd.DatetimeTZDtype):
            out[column] = out[column].dt.tz_localize(None)
    return out
