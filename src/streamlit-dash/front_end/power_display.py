import os
import psutil
import streamlit as st

def is_script_running(script_filename: str) -> bool:
    """
    Return True if any process command line includes this script
    (e.g. "trendline.py"). Works on Windows and Linux with psutil.
    """
    target = script_filename.strip().lower()
    if not target:
        return False

    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            for arg in cmdline:
                if os.path.basename(str(arg)).lower() == target:
                    return True
                # e.g. full path: /home/user/proj/trendline.py
                if str(arg).lower().endswith("/" + target) or str(arg).lower().endswith("\\" + target):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

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

    RenderTrendlinePower(is_script_running("trendline.py"))
