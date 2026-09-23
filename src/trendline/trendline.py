
from news_service import NewsScrapingService, PendingSentimentAnalysis
from sentiment_service import SentimentService
from timing_service import TimingService
from trend_core.base.tl_logger import LoggingService
from trend_core.trader import StockTrader
from trend_core.configs import BASE_PURCHASE_DOLLARS, BASE_PURCHASE_QTY
from trade_manager import TradeManager, PendingBuy, PendingSell
from trend_core.configs import OLLAMA_WARMUP_ON_STARTUP
from trend_core.database.db_service import DatabaseService
import atexit
import signal
import sys
from alpaca.trading.enums import TimeInForce
from alpaca.trading.models import Order
from datetime import datetime, timezone
from heartbeat_service import HeartbeatService
def _shutdown_persist() -> None:
    database_service.close()


def _handle_stop_signal(signum, frame) -> None:
    database_service.close()
    sys.exit(0)

database_service = DatabaseService()
sentiment_service = SentimentService()  # analyzes the sentiment of news headlines
news_scraper = NewsScrapingService(skip_initial_scrape=True)  # state restored by PersistentDataService when present
timing_service = TimingService()  # keeps track of the period of the app. Uses a set time from configs
logger = LoggingService()  # for logging information
stock_trader = StockTrader()  # used to buy and sell stocks through Alpaca-py
trade_manager = TradeManager()  # manages full trade lifecycle: news archival, sentiment, buy/sell order tracking, hold timing
heartbeat = HeartbeatService()

atexit.register(_shutdown_persist)
if hasattr(signal, "SIGINT"):
    signal.signal(signal.SIGINT, _handle_stop_signal)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _handle_stop_signal)


if OLLAMA_WARMUP_ON_STARTUP:
    logger.log_info("Warming up Ollama sentiment service (non-fatal).")
    sentiment_service.warmup()

database_service.open()
while True:
    """
    Buying Logic
    ------------
    Scrape the news periodically as defined by the timing service.
    
    If there is new news, analyze the sentiment of the headlines.

    For each positive sentiment headline, buy a fixed amount of that company as defined by BASE_PURCHASE_DOLLARS.

    Finally, log the order with the trade manager which archives the news entry and tracks the buy order.
    
    """
    heartbeat.pulse()
    if timing_service.is_time_to_scrape():
        logger.purge_old_logs()
        news_scraper.update()
        articles: list[PendingSentimentAnalysis] = news_scraper.get_new_articles()
        logger.log_info(f"Found {len(articles)} new articles.")
        for article in articles:
            heartbeat.pulse()
            if article.title=="" or article.title is None:
                sentiment_service.archive_no_title(article.article_id)
                logger.log_warning(f"No headline found for article. {article.article_id}")
                continue
            try:
                sentiment_service.analyze_sentiment(article.title, article.article_id)
            except Exception as e:
                # SentimentService is intended to never raise, but guard the main loop regardless.
                logger.log_error(f"SentimentService crashed: {type(e).__name__}: {e}")


            #get all the tickers that need to be purchased
            pending_buys: list[PendingBuy] = trade_manager.get_pending_buys()
            orders = []
            for buy in pending_buys:
                order: Order | None = stock_trader.buy(
                    buy.ticker, quantity=BASE_PURCHASE_QTY, time_in_force=TimeInForce.GTC
                )
                orders.append(order)
                #create buy entry in purchase table now?
            # if rows:
            #     logger.log_info(
            #         f"Buys for headline: {len(buy_orders)}/{len(tickers)} filled "
            #         f"({','.join(tickers)}) — {entry.get('title', '')[:80]!r}"
            #     )

            trade_manager.archive_buy(pending_buys, orders)

        timing_service.mark_scrape_completed()

    else:
        timing_service.wait_until_next_scrape()



    """
    Selling Logic
    -------------

    All stock purchased by this program has been logged in the trade_manager.

    The trade manager knows when each stock purchase order was fulfilled.

    Each iteration of this program, we check to see if the purchase order was fulfilled more than a set amount of time ago.
    If it was, then that order is returned by trade_manager.check_ready_to_sell()

    """
    trade_manager.update()

    ready_to_sell: list[PendingSell] = trade_manager.query_ready_to_sell()

    sell_orders = []
    for stock in ready_to_sell:
        sell_order: Order = stock_trader.sell(stock.ticker, quantity=stock.qty, time_in_force=TimeInForce.GTC)
        sell_orders.append(sell_order)

    trade_manager.archive_sell(ready_to_sell, sell_orders)


