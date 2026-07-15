from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
    """Parse mixed feed dates into timezone-aware UTC timestamps.

    Values that cannot be parsed become ``NaT``. Feed timestamps without an
    explicit offset are treated as UTC by pandas. This assumption is explicit
    and is covered by QA through the invalid-publication-date count.
    """
    return pd.to_datetime(values, errors="coerce", utc=True, format="mixed")


def _first_existing_series(df: pd.DataFrame, candidates: Iterable[str]) -> pd.Series:
    for column in candidates:
        if column in df.columns:
            return df[column]
    return pd.Series("", index=df.index, dtype="object")


def add_published_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add canonical UTC and Cambodia publication timestamps."""
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
    if not 0 <= hour <= 23:
        raise ValueError("Daily boundary hour must be between 0 and 23.")

    current = ensure_cambodia_datetime(now)
    boundary = current.replace(hour=hour, minute=0, second=0, microsecond=0)
    if current < boundary:
        boundary -= timedelta(days=1)
    return boundary


def daily_window(now: datetime, *, boundary_hour: int = 9) -> tuple[datetime, datetime]:
    """Return the completed half-open daily window ``[start, end)``."""
    end = latest_daily_boundary(now, hour=boundary_hour)
    return end - timedelta(days=1), end


def daily_report_date(now: datetime, *, boundary_hour: int = 9) -> date:
    """Return the reporting date represented by the completed daily window.

    The report date is the Cambodia calendar date of the window's exclusive
    end boundary. At or after 09:00 on 14 July, the report date is 14 July.
    Before 09:00 on 14 July, the latest completed report date is 13 July.
    """
    _, end = daily_window(now, boundary_hour=boundary_hour)
    return end.date()


def rolling_window(
    now: datetime,
    *,
    days: int = 0,
    hours: int = 0,
) -> tuple[datetime, datetime]:
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
