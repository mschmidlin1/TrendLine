import sys
import os
import tomllib
from pathlib import Path
from datetime import timedelta
MARKET_HOLD_TIME = timedelta(days=5, hours=3)
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

RSS_FEED_URLS = {
    #"Reuters": "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best/",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "WallStreetJournal": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "FinancialTimes": "https://www.ft.com/global-economy?format=rss",
    "TheEconomist": "https://www.economist.com/business/rss.xml"
    }