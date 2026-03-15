import sys
import os
import tomllib
from pathlib import Path

#logging settings
secrets_path = Path(".streamlit/secrets.toml")
config = None
with open(secrets_path, "rb") as f:
    config = tomllib.load(f)

HF_TOKEN = config["HF_TOKEN"]
ALPACA_SECRET_KEY = config["ALPACA_SECRET_KEY"]
ALPACA_SECRET_KEY_PAPER = config["ALPACA_SECRET_KEY_PAPER"]
ALPACA_CHOSEN_SECRET_KEY = ALPACA_SECRET_KEY_PAPER

FILE_LOG_LEVEL = "DEBUG"
STDOUT_LOG_LEVEL = "INFO"
LOG_FILE = "logs.txt"
LOG_PATH = "logs"

NEWS_URLS = []