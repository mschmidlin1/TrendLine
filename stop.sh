#!/usr/bin/env bash
# Stops services started by run.sh (PID files + ngrok pattern).
# Mirrors stop_front_backend_ngrok.bat.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PORT_FILE="$SCRIPT_DIR/.trendline_port"
SAVED_PORT=""
if [[ -f "$PORT_FILE" ]]; then
  SAVED_PORT="$(tr -d '[:space:]' <"$PORT_FILE" || true)"
fi

for name in backend streamlit ngrok; do
  f="$SCRIPT_DIR/.trendline_${name}.pid"
  if [[ -f "$f" ]]; then
    pid="$(tr -d '[:space:]' <"$f" || true)"
    if [[ -n "$pid" ]] && kill "$pid" 2>/dev/null; then
      :
    fi
    rm -f "$f"
  fi
done

# ngrok may outlive the PID file or run without one
pkill -f "ngrok http.*trendline:1234water" 2>/dev/null || true

# Streamlit child processes if the saved parent PID was insufficient
if [[ -n "$SAVED_PORT" ]]; then
  pkill -f "streamlit run front_app.py --server.port ${SAVED_PORT}" 2>/dev/null || true
fi

rm -f "$PORT_FILE"

echo "Stopped TrendLine backend / Streamlit / ngrok (where found)."
echo "If something is still running, close its terminal or use: ps aux | grep -E 'main.py|streamlit|ngrok'"
