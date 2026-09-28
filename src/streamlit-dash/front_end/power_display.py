from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from trend_core.configs import HEARTBEAT_PULSE_FREQUENCY_SECONDS
from trend_core.database.db_service import DatabaseService

_HEARTBEAT_STALE_AFTER = timedelta(seconds=3 * HEARTBEAT_PULSE_FREQUENCY_SECONDS)

_HEARTBEAT_SQL = """
SELECT last_seen, now() AS db_now
FROM heartbeat
WHERE id = 1
"""


def _ensure_database_open(db: DatabaseService) -> None:
    # open() replaces _conn without closing it, so only connect when needed.
    conn = db._conn
    if conn is None or conn.closed:
        db.open()


def is_heartbeat_fresh() -> bool:
    """True when heartbeat.last_seen is within three pulse intervals of the database clock."""
    try:
        db = DatabaseService()
        _ensure_database_open(db)
        row = db.fetch_one(_HEARTBEAT_SQL)
        if not row:
            return False
        last_seen, db_now = row[0], row[1]
        if not isinstance(last_seen, datetime) or not isinstance(db_now, datetime):
            return False
        return (db_now - last_seen) <= _HEARTBEAT_STALE_AFTER
    except Exception:
        return False


def RenderTrendlinePower(running: bool):
    color = "#22c55e" if running else "#6b7280"
    label = "Running" if running else "Off"
    st.markdown(
        f'<div style="display:flex;justify-content:flex-end;align-items:center;width:100%;">'
        f'<span style="display:inline-flex;align-items:center;gap:8px;">'
        f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;'
        f'background:{color};box-shadow:0 0 6px {color};"></span>'
        f'<span style="font-size:0.9rem;">{label}</span>'
        f"</span></div>",
        unsafe_allow_html=True,
    )


def render_power_display():
    """"""

    RenderTrendlinePower(is_heartbeat_fresh())
