#!/usr/bin/env bash
# TrendLine launcher (Linux): backend, Streamlit on a random port, ngrok with basic auth.
# Mirrors run_front_backend_ngrok.bat. Requires .venv and (for separate windows) a GUI session.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_ACTIVATE="$SCRIPT_DIR/.venv/bin/activate"
if [[ ! -f "$VENV_ACTIVATE" ]]; then
  echo "Missing virtualenv: $VENV_ACTIVATE" >&2
  echo "Create it with: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

# Random port in dynamic/private range (49152–65535)
PORT=$((49152 + RANDOM % 16384))
export TRENDLINE_ROOT="$SCRIPT_DIR"
export TRENDLINE_PORT="$PORT"
echo "$PORT" > "$SCRIPT_DIR/.trendline_port"

echo ""
echo "TrendLine launcher"
echo "------------------"
echo "Streamlit + ngrok will use port: $PORT"
echo "Basic auth: trendline / 1234water"
echo ""

wrap_py_service() {
  local name="$1"
  local run="$2"
  printf 'source "%s" && %s & echo $! > "%s/.trendline_%s.pid"; wait $!; exec bash' \
    "$VENV_ACTIVATE" "$run" "$TRENDLINE_ROOT" "$name"
}

wrap_ngrok() {
  printf 'ngrok http %s --basic-auth=trendline:1234water & echo $! > "%s/.trendline_ngrok.pid"; wait $!; exec bash' \
    "$TRENDLINE_PORT" "$TRENDLINE_ROOT"
}

gui_terminal_available() {
  [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] || return 1
  command -v gnome-terminal &>/dev/null && return 0
  command -v konsole &>/dev/null && return 0
  command -v xfce4-terminal &>/dev/null && return 0
  command -v x-terminal-emulator &>/dev/null && return 0
  command -v xterm &>/dev/null && return 0
  return 1
}

try_open_terminal() {
  local title="$1"
  local inner="$2"

  if command -v gnome-terminal &>/dev/null; then
    gnome-terminal --title="$title" --working-directory="$SCRIPT_DIR" -- bash -c "$inner"
    return 0
  fi
  if command -v konsole &>/dev/null; then
    konsole --title "$title" --workdir "$SCRIPT_DIR" -e bash -c "$inner" &
    return 0
  fi
  if command -v xfce4-terminal &>/dev/null; then
    xfce4-terminal --title="$title" --working-directory="$SCRIPT_DIR" -x bash -c "$inner" &
    return 0
  fi
  if command -v x-terminal-emulator &>/dev/null; then
    x-terminal-emulator -T "$title" -e bash -c "$inner" &
    return 0
  fi
  if command -v xterm &>/dev/null; then
    xterm -title "$title" -cd "$SCRIPT_DIR" -e bash -c "$inner" &
    return 0
  fi

  return 1
}

run_fallback_background() {
  mkdir -p "$SCRIPT_DIR/logs"
  # shellcheck source=/dev/null
  source "$VENV_ACTIVATE"
  python main.py >>"$SCRIPT_DIR/logs/trendline_backend.log" 2>&1 &
  echo $! >"$SCRIPT_DIR/.trendline_backend.pid"
  sleep 2
  streamlit run front_app.py --server.port "$TRENDLINE_PORT" >>"$SCRIPT_DIR/logs/trendline_streamlit.log" 2>&1 &
  echo $! >"$SCRIPT_DIR/.trendline_streamlit.pid"
  sleep 3
  ngrok http "$TRENDLINE_PORT" --basic-auth=trendline:1234water >>"$SCRIPT_DIR/logs/trendline_ngrok.log" 2>&1 &
  echo $! >"$SCRIPT_DIR/.trendline_ngrok.pid"
  echo "Logs: logs/trendline_backend.log, logs/trendline_streamlit.log, logs/trendline_ngrok.log"
}

INNER_BACKEND="$(wrap_py_service backend "python main.py")"
INNER_STREAMLIT="$(wrap_py_service streamlit "streamlit run front_app.py --server.port ${TRENDLINE_PORT}")"
INNER_NGROK="$(wrap_ngrok)"

if gui_terminal_available; then
  if try_open_terminal "TrendLine Backend" "$INNER_BACKEND"; then
    sleep 2
    if try_open_terminal "TrendLine Streamlit" "$INNER_STREAMLIT"; then
      sleep 3
      if try_open_terminal "TrendLine ngrok" "$INNER_NGROK"; then
        echo "Started backend, Streamlit (port $PORT), and ngrok in separate windows."
        echo "To stop all: run ./stop.sh, or close each terminal window."
        exit 0
      fi
    fi
  fi
  echo "Could not open all terminal windows. Close any partial TrendLine windows, then retry or run with SSH/headless (no DISPLAY) for background mode." >&2
  exit 1
fi

echo "No GUI terminal session or emulator found; starting in background."
run_fallback_background
echo "To stop all: run ./stop.sh"
exit 0
