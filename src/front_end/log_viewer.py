from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
from filelock import FileLock
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode


_LEVEL_COLORS: Dict[str, str] = {
    "ERROR": "#d32f2f",
    "WARNING": "#f57c00",
    "INFO": "#2e7d32",
    "DEBUG": "#1976d2",
}

_LINE_RE = re.compile(r"^(?P<ts>.+?) - (?P<level>[A-Z]+) - (?P<msg>.*)$")

_LOG_GRID_HEIGHT = 420
_UNKNOWN_COLOR = "#616161"


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


def _read_log_lines(path: Path, lock_path: Path, timeout_s: float = 60.0) -> List[str]:
    if not path.is_file():
        return []

    lock = FileLock(str(lock_path), timeout=timeout_s)
    lock.acquire()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    finally:
        lock.release()


def _parse_line(line: str) -> Tuple[str, str, str]:
    """
    Returns (level, ts, msg). If parse fails, level is 'UNKNOWN'.
    """
    m = _LINE_RE.match(line)
    if not m:
        return ("UNKNOWN", "", line)
    ts = m.group("ts")
    level = m.group("level")
    msg = m.group("msg")
    return (level, ts, msg)


def _lines_to_sorted_dataframe(lines: List[str]) -> pd.DataFrame:
    rows: List[dict] = []
    for ln in lines:
        level, ts, msg = _parse_line(ln)
        parsed = pd.to_datetime(ts, errors="coerce") if ts else pd.NaT
        datetime_display = ts if ts else "—"
        rows.append(
            {
                "_dt": parsed,
                "Datetime": datetime_display,
                "Level": level,
                "Message": msg,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["Datetime", "Level", "Message"])
    df = df.sort_values("_dt", ascending=False, na_position="last")
    return df.drop(columns=["_dt"]).reset_index(drop=True)


def render_log_viewer() -> None:
    st.subheader("Log Viewer")


    if "log_df" not in st.session_state or "grid_options" not in st.session_state:
        with st.spinner("Getting Log data...", show_time=True):
            log_path = Path("logs") / "logs.txt"
            lock_path = Path("logs") / "logs.txt.lock"
            lines = _read_log_lines(log_path, lock_path)

            if not lines:
                st.warning("Log file not found yet (expected `logs/logs.txt`).")
                return

            df = _lines_to_sorted_dataframe(lines)

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
