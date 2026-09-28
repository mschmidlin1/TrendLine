from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Sequence

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

from trend_core.base.datetime_utils import convert_series_to_display_tz
from trend_core.configs import DISPLAY_TIMEZONE_NAME, LOG_VIEWER_MAX_LINES
from trend_core.database.db_service import DatabaseService


_LEVEL_COLORS: Dict[str, str] = {
    "ERROR": "#d32f2f",
    "WARNING": "#f57c00",
    "INFO": "#2e7d32",
    "DEBUG": "#1976d2",
}

_LOG_GRID_HEIGHT = 420
_UNKNOWN_COLOR = "#616161"

_LOGS_SQL = """
SELECT created_at, level, message
FROM logs
ORDER BY created_at DESC
LIMIT %s
"""


def _row_style_js() -> JsCode:
    branches = "\n".join(
        f'    if (L === "{level}") {{ return {{ color: "{color}" }}; }}'
        for level, color in _LEVEL_COLORS.items()
    )
    code = f"""
function(params) {{
    if (!params.data) {{
        return {{}};
    }}
    var L = params.data.Level;
{branches}
    return {{ color: "{_UNKNOWN_COLOR}" }};
}}
"""
    return JsCode(code)


def _ensure_database_open(db: DatabaseService) -> None:
    # open() replaces _conn without closing it, so only connect when needed.
    conn = db._conn
    if conn is None or conn.closed:
        db.open()


def _format_display_time(value: object) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except TypeError:
        pass
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _rows_to_dataframe(rows: Sequence[Sequence[Any]]) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(list(rows), columns=["created_at", "level", "message"])
    if frame.empty:
        return pd.DataFrame(columns=["Datetime", "Level", "Message"])
    displayed = convert_series_to_display_tz(frame["created_at"], DISPLAY_TIMEZONE_NAME)
    return pd.DataFrame(
        {
            "Datetime": [_format_display_time(value) for value in displayed],
            "Level": frame["level"].map(lambda value: "" if value is None else str(value)),
            "Message": frame["message"].map(lambda value: "" if value is None else str(value)),
        }
    )


def _load_log_rows() -> list:
    db = DatabaseService()
    _ensure_database_open(db)
    rows = db.fetch_all(_LOGS_SQL, (LOG_VIEWER_MAX_LINES,))
    return list(rows)


def render_log_viewer() -> None:
    st.subheader("Log Viewer")

    if "log_df" not in st.session_state or "grid_options" not in st.session_state:
        with st.spinner("Getting Log data...", show_time=True):
            try:
                rows = _load_log_rows()
            except Exception:
                st.warning("Could not load logs from the database.")
                return

            if not rows:
                st.warning("No log rows in the database yet.")
                return

            df = _rows_to_dataframe(rows)

            gb = GridOptionsBuilder.from_dataframe(df)
            gb.configure_default_column(
                filter="agTextColumnFilter",
                floatingFilter=True,
                resizable=True,
                sortable=True,
                cellStyle={"fontFamily": "monospace"},
            )
            gb.configure_column("Datetime", width=200, maxWidth=280)
            gb.configure_column("Level", width=110, maxWidth=140)
            gb.configure_column("Message", flex=1, minWidth=240, wrapText=True)
            gb.configure_grid_options(getRowStyle=_row_style_js())
            grid_options = gb.build()
            st.session_state["log_df"] = df
            st.session_state["grid_options"] = grid_options

    AgGrid(
        st.session_state["log_df"],
        gridOptions=st.session_state["grid_options"],
        height=_LOG_GRID_HEIGHT,
        theme="streamlit",
        key="log_grid",
        update_on=[],
        allow_unsafe_jscode=True,
        show_toolbar=True,
        show_search=True,
        show_download_button=True,
    )
