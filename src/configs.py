import sys
import os
import tomllib
from pathlib import Path
from datetime import timedelta
MARKET_HOLD_TIME = timedelta(days=0, hours=4)
SCRAPE_FREQUENCY = timedelta(minutes=10)
# Display timezone for Streamlit (US equity session; matches MarketMonitorService US/Eastern)
DISPLAY_TIMEZONE_NAME = "America/New_York"
BASE_PURCHASE_DOLLARS = 10.0
BASE_PURCHASE_QTY = 1
#logging settings
secrets_path = Path(".streamlit/secrets.toml")
config = None
with open(secrets_path, "rb") as f:
    config = tomllib.load(f)

USE_PAPER = True

HF_TOKEN = config["HF_TOKEN"]
ALPACA_SECRET_KEY = config["ALPACA_SECRET_KEY"]
ALPACA_SECRET_KEY_PAPER = config["ALPACA_SECRET_KEY_PAPER"]
ALPACA_API_ID = config["ALPACA_API_ID"]
ALPACA_API_ID_PAPER = config["ALPACA_API_ID_PAPER"]

ALPACA_CHOSEN_SECRET_KEY = None
ALPACA_CHOSEN_API_ID = None
USE_PAPER = True
if USE_PAPER:
    ALPACA_CHOSEN_SECRET_KEY = ALPACA_SECRET_KEY_PAPER
    ALPACA_CHOSEN_API_ID = ALPACA_API_ID_PAPER
else:
    ALPACA_CHOSEN_SECRET_KEY = ALPACA_SECRET_KEY
    ALPACA_CHOSEN_API_ID = ALPACA_API_ID

FILE_LOG_LEVEL = "DEBUG"
STDOUT_LOG_LEVEL = "INFO"
LOG_FILE = "logs.txt"
LOG_PATH = "logs"
LOG_VIEWER_MAX_LINES = 5000

# On-disk snapshots for PersistentDataService (project root relative)
PERSISTENT_DATA_DIR = Path("persistent_data")

RSS_FEED_URLS = {
    #"Reuters": "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best/",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "WallStreetJournal": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "FinancialTimes": "https://www.ft.com/global-economy?format=rss",
    "TheEconomist": "https://www.economist.com/business/rss.xml"
    }

# Ollama / SentimentService settings (env-overridable)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
# Total attempts per sentiment prediction (including the first try).
OLLAMA_MAX_ATTEMPTS = int(os.getenv("OLLAMA_MAX_ATTEMPTS", "3"))
# Exponential backoff base in seconds. Sleep is applied after failed attempts 1..(max-1).
OLLAMA_RETRY_BACKOFF_SECONDS = float(os.getenv("OLLAMA_RETRY_BACKOFF_SECONDS", "0.75"))
# Optional hard timeout (seconds) for the Ollama client request. Empty/0 disables.
_ollama_timeout_raw = os.getenv("OLLAMA_TIMEOUT_SECONDS", "").strip()
OLLAMA_TIMEOUT_SECONDS = float(_ollama_timeout_raw) if _ollama_timeout_raw not in ("", "0") else None
# If true, `trendline.py` will attempt a non-fatal warmup on startup.
OLLAMA_WARMUP_ON_STARTUP = os.getenv("OLLAMA_WARMUP_ON_STARTUP", "1").strip() not in ("0", "false", "False")