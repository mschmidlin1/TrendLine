from src.market_monitor import MarketMonitorService
from src.news_scraper import NewsScrapingService
from src.sentiment_service import SentimentService
from src.base.sentiment_response import SentimentResponse
from src.timing_service import TimingService
from src.base.tl_logger import LoggingService
from src.trader import StockTrader
from src.configs import BASE_PURCHASE_DOLLARS, BASE_PURCHASE_QTY
from src.trade_lifecycle_manager import TradeLifecycleManager
from src.persistent_data_service import PersistentDataService

import atexit
import signal
import sys
import time
from alpaca.trading.enums import TimeInForce
from alpaca.trading.models import Order
from typing import List


def _shutdown_persist() -> None:
    PersistentDataService().save_all(reason="shutdown")


def _handle_stop_signal(signum, frame) -> None:
    PersistentDataService().save_all(reason="shutdown")
    sys.exit(0)


sentiment_service = SentimentService()  # analyzes the sentiment of news headlines
news_scraper = NewsScrapingService(skip_initial_scrape=True)  # state restored by PersistentDataService when present
market_monitor = MarketMonitorService()  # tells you if the market is open and how long until it opens
timing_service = TimingService()  # keeps track of the period of the app. Uses a set time from configs
logger = LoggingService()  # for logging information
stock_trader = StockTrader()  # used to buy and sell stocks through Alpaca-py
trade_manager = TradeLifecycleManager()  # manages full trade lifecycle: news archival, sentiment, buy/sell order tracking, hold timing
persistent_data = PersistentDataService()
persistent_data.load_all()

atexit.register(_shutdown_persist)
if hasattr(signal, "SIGINT"):
    signal.signal(signal.SIGINT, _handle_stop_signal)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _handle_stop_signal)


ready_to_sell_orders: List[Order] = []

while True:
    """
    Buying Logic
    ------------
    Scrape the news periodically as defined by the timing service.
    
    If there is new news, analyze the sentiment of the headlines.

    For each positive sentiment headline, buy a fixed amount of that company as defined by BASE_PURCHASE_DOLLARS.

    Finally, log the order with the trade manager which archives the news entry and tracks the buy order.
    
    """
    if timing_service.is_time_to_scrape():
        news_scraper.update()
        article_tuples = news_scraper.get_unserved_articles()
        logger.log_info(f"Found {len(article_tuples)} new articles.")
        for name, entry in article_tuples:
            if entry.get('title')=="" or entry.get('title') is None:
                logger.log_warning(f"No headline found for article. {name} --- {entry.get('link', '')}")
                continue
            sentiment_response: SentimentResponse = sentiment_service.analyze_sentiment(entry.get('title'))

            # Initialize buy_order as None
            buy_order = None

            if sentiment_response.format_match and sentiment_response.ticker_found: #this means the data is actionable
                if sentiment_response.sentiment == "positive":
                    order: Order = stock_trader.buy(sentiment_response.ticker, quantity=BASE_PURCHASE_QTY, time_in_force=TimeInForce.GTC)
                    if order is not None:
                        buy_order = order  # Store for archival

            # Archive with or without buy order — buy orders are automatically tracked for hold timing
            trade_manager.archive_news_entry(name, entry, sentiment_response, buy_order)

        timing_service.mark_scrape_completed()

    else:
        wait_time_seconds = timing_service.time_until_next_scrape()
        formatted_wait_time = f"{int(wait_time_seconds // 60)}m {wait_time_seconds % 60:.1f}s"
        logger.log_info(f"Sleeping until next iteration: {formatted_wait_time}")
        time.sleep(wait_time_seconds)
        logger.log_info(f"Woke up, proceeding with next iteration")



    """
    Selling Logic
    -------------

    All stock purchased by this program has been logged in the trade_manager.

    The trade manager knows when each stock purchase order was fulfilled.

    Each iteration of this program, we check to see if the purchase order was fulfilled more than a set amount of time ago.
    If it was, then that order is returned by trade_manager.check_ready_to_sell()

    """
    trade_manager.update()

    ready_to_sell_orders: List[Order] = trade_manager.check_ready_to_sell()
    trade_manager.clear_ready_to_sell()

    for buy_order in ready_to_sell_orders:
        sell_order: Order = stock_trader.sell(buy_order.symbol, quantity=int(buy_order.qty), time_in_force=TimeInForce.GTC)
        if sell_order is not None:
            trade_manager.log_sell_order(buy_order, sell_order)

    persistent_data.save_all(reason="flush")


