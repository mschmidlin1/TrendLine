from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd


def display_zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize a datetime to UTC (naive uses local→UTC via timestamp(); aware uses astimezone)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return naive_local_to_utc(dt)
    return dt.astimezone(timezone.utc)


def naive_local_to_utc(dt: datetime) -> datetime:
    """
    Convert archived_at from legacy snapshots: naive datetimes were local wall time
    (from datetime.now()); aware datetimes are normalized to UTC.
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    return datetime.fromtimestamp(dt.timestamp(), tz=timezone.utc)


def to_display_timezone(dt: Optional[datetime], tz: ZoneInfo) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def convert_series_to_display_tz(series: pd.Series, tz_name: str) -> pd.Series:
    """Convert UTC (or naive-as-UTC) datetimes in a column to the named IANA zone for UI."""
    tz = ZoneInfo(tz_name)

    def _one(x: object):
        if x is None:
            return pd.NA
        try:
            if pd.isna(x):
                return pd.NA
        except TypeError:
            pass
        if isinstance(x, pd.Timestamp):
            x = x.to_pydatetime()
        elif not isinstance(x, datetime):
            x = pd.to_datetime(x, utc=True).to_pydatetime()
        return to_display_timezone(x, tz)

    return series.apply(_one)
