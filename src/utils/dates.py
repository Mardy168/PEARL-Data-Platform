from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Tuple

import pandas as pd

CAMBODIA_TZ = timezone(timedelta(hours=7))
DISPLAY_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_cambodia() -> datetime:
    return datetime.now(CAMBODIA_TZ)


def parse_datetime_series(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, errors="coerce", utc=True)


def add_published_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    source = out.get("published_date", out.get("Published Date", pd.Series("", index=out.index, dtype="object")))
    out["published_dt_utc"] = parse_datetime_series(source)
    out["published_dt_kh"] = out["published_dt_utc"].dt.tz_convert(CAMBODIA_TZ)
    out["Published Date"] = out["published_dt_kh"].dt.strftime(DISPLAY_DATE_FORMAT).fillna("")
    return out


def rolling_window(now: datetime, *, days: int = 0, hours: int = 0) -> Tuple[datetime, datetime]:
    return now - timedelta(days=days, hours=hours), now


def previous_month_window(now: datetime) -> Tuple[datetime, datetime, str]:
    first_current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_day = first_current - timedelta(days=1)
    first_previous = previous_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first_previous, first_current, first_previous.strftime("%Y-%m")


def remove_timezone_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if isinstance(out[col].dtype, pd.DatetimeTZDtype):
            out[col] = out[col].dt.tz_localize(None)
    return out
