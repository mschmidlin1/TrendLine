from datetime import datetime, timezone
from src.base.singleton import SingletonMeta
from src.base.sentiment_response import SentimentResponse
from src.base.tl_logger import LoggingService
from src.base.alpaca_client import AlpacaClient
from src.configs import MARKET_HOLD_TIME
from src.base.datetime_utils import ensure_utc, naive_local_to_utc
from alpaca.trading.client import TradingClient
from alpaca.trading.models import Order
from alpaca.trading.enums import OrderStatus
import pandas as pd
from typing import List, Dict, Optional, Any


class TradeLifecycleManager(metaclass=SingletonMeta):
    """
    Singleton service that manages the complete trade lifecycle: archiving news articles
    with their sentiment analysis results, tracking buy orders through fill and hold periods,
    determining when positions are ready to sell, logging sell orders, and tracking sell order
    completion.

    Attributes:
        _logger (LoggingService): Logger instance for tracking operations.
        alpaca_client (AlpacaClient): Singleton Alpaca client instance.
        trading_client (TradingClient): Alpaca trading client for API calls.
        archived_entries (List[Dict[str, Any]]): Main storage for archived news entries.
        _article_id_index (Dict[str, int]): Index mapping article_id to position in archived_entries.
        _buy_order_id_index (Dict[str, str]): Index mapping buy order ID to article_id.
        ready_to_sell (List[Order]): Buy orders whose hold period has elapsed.

    Note:
        ``archived_at`` on each entry is timezone-aware UTC (``datetime`` with ``timezone.utc``).
    """

    TERMINAL_STATUSES = {
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.REJECTED
    }

    def __init__(self) -> None:
        """Initialize the TradeLifecycleManager service."""
        self._logger = LoggingService()
        self.alpaca_client = AlpacaClient()
        self.trading_client: TradingClient = self.alpaca_client.trading_client
        self.archived_entries: List[Dict[str, Any]] = []
        self._article_id_index: Dict[str, int] = {}
        self._buy_order_id_index: Dict[str, str] = {}
        self.ready_to_sell: List[Order] = []

    def get_persistent_snapshot(self) -> Dict[str, Any]:
        """Return in-memory state to be persisted across restarts."""
        return {
            'archived_entries': self.archived_entries,
            '_article_id_index': self._article_id_index,
            '_buy_order_id_index': self._buy_order_id_index,
            'ready_to_sell': self.ready_to_sell,
        }

    def restore_from_persistent_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Restore state from :meth:`get_persistent_snapshot`."""
        required = ('archived_entries', '_article_id_index', '_buy_order_id_index', 'ready_to_sell')
        for key in required:
            if key not in snapshot:
                raise ValueError(f"Invalid persistent snapshot: missing '{key}'")
        self.archived_entries = snapshot['archived_entries']
        self._article_id_index = snapshot['_article_id_index']
        self._buy_order_id_index = snapshot['_buy_order_id_index']
        self.ready_to_sell = snapshot['ready_to_sell']
        for entry in self.archived_entries:
            at = entry.get("archived_at")
            if isinstance(at, datetime) and at.tzinfo is None:
                entry["archived_at"] = naive_local_to_utc(at)
            elif isinstance(at, datetime):
                entry["archived_at"] = at.astimezone(timezone.utc)

    def archive_news_entry(
        self,
        source_name: str,
        article_entry,
        sentiment_response: SentimentResponse,
        buy_order: Optional[Order] = None
    ) -> bool:
        """
        Archive a news article with its sentiment analysis and optional buy order.

        When a buy_order is provided, it is automatically tracked for hold-period timing
        (replacing the need for a separate OrderTracker.log_purchase() call).

        Args:
            source_name (str): Name of the RSS feed source.
            article_entry: Complete RSS feed entry from feedparser (FeedParserDict).
            sentiment_response (SentimentResponse): Sentiment analysis result.
            buy_order (Optional[Order]): Buy order if purchase was made (default: None).

        Returns:
            bool: True if archived successfully, False if duplicate or missing link.
        """
        # Extract article_id from article_entry
        article_id = article_entry.get('link')
        if article_id is None or article_id == '':
            self._logger.log_error(
                f"Cannot archive entry from {source_name}: missing 'link' field in article_entry."
            )
            return False

        # Check for duplicate
        if article_id in self._article_id_index:
            self._logger.log_warning(
                f"Duplicate article_id '{article_id}' — entry already archived. Skipping."
            )
            return False

        # Create archived entry
        entry = {
            'article_id': article_id,
            'source_name': source_name,
            'article_entry': article_entry,
            'sentiment_response': sentiment_response,
            'buy_order': buy_order,
            'sell_order': None,
            'archived_at': datetime.now(timezone.utc),
            'resulted_in_purchase': buy_order is not None,
            'buy_order_terminal': buy_order is None,  # True if no buy order (nothing to track)
            'sell_order_terminal': True,  # No sell order yet, nothing to track
        }

        # Append and index
        self.archived_entries.append(entry)
        self._article_id_index[article_id] = len(self.archived_entries) - 1

        # Index buy order if present
        if buy_order is not None:
            self._buy_order_id_index[str(buy_order.id)] = article_id

        self._logger.log_info(
            f"Archived entry from {source_name}: '{article_entry.get('title', 'N/A')}' "
            f"(purchase={'Yes' if buy_order is not None else 'No'})"
        )
        return True

    def log_sell_order(self, buy_order: Order, sell_order: Order) -> bool:
        """
        Log a sell order against the archive entry that contains the corresponding buy order.

        Args:
            buy_order (Order): The original buy order object (used to look up the archive entry).
            sell_order (Order): The sell order object from Alpaca.

        Returns:
            bool: True if sell order was logged successfully, False if buy order not found.
        """
        buy_order_id_str = str(buy_order.id)

        # Look up article_id by buy order ID
        article_id = self._buy_order_id_index.get(buy_order_id_str)
        if article_id is None:
            self._logger.log_error(
                f"Cannot log sell order: buy order ID '{buy_order_id_str}' not found in archive."
            )
            return False

        # Look up the archive entry
        entry_index = self._article_id_index[article_id]
        entry = self.archived_entries[entry_index]

        # Warn if overwriting existing sell order
        if entry['sell_order'] is not None:
            self._logger.log_warning(
                f"Overwriting existing sell order for article '{article_id}' "
                f"(old sell order ID: {entry['sell_order'].id})."
            )

        # Set sell order and mark as non-terminal (needs tracking)
        entry['sell_order'] = sell_order
        entry['sell_order_terminal'] = False

        self._logger.log_info(
            f"Logged sell order {sell_order.id} for {sell_order.symbol} "
            f"against buy order {buy_order_id_str}."
        )
        return True

    def update(self) -> None:
        """
        Update all order statuses from Alpaca and manage buy order hold-period timing.

        This consolidates the update logic from both the former OrderTracker and
        SellTrackingService. It:
        1. Refreshes non-terminal buy orders from Alpaca
        2. Checks filled buy orders against MARKET_HOLD_TIME for ready-to-sell
        3. Refreshes non-terminal sell orders from Alpaca
        """
        for entry in self.archived_entries:
            # --- Buy order tracking ---
            if not entry['buy_order_terminal']:
                try:
                    updated_buy_order = self.trading_client.get_order_by_id(
                        entry['buy_order'].id
                    )
                    entry['buy_order'] = updated_buy_order

                    if updated_buy_order.status == OrderStatus.FILLED:
                        filled_utc = ensure_utc(updated_buy_order.filled_at)
                        if filled_utc is not None:
                            sell_time = filled_utc + MARKET_HOLD_TIME
                            if datetime.now(timezone.utc) >= sell_time:
                                self.ready_to_sell.append(updated_buy_order)
                                entry['buy_order_terminal'] = True
                                self._logger.log_info(
                                    f"Buy order for {updated_buy_order.symbol} (ID: {updated_buy_order.id}) "
                                    f"filled and hold period elapsed. Added to ready_to_sell."
                                )
                        # else: hold period not yet elapsed, keep buy_order_terminal as False
                    elif updated_buy_order.status in (
                        OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED
                    ):
                        entry['buy_order_terminal'] = True
                        self._logger.log_warning(
                            f"Buy order for {updated_buy_order.symbol} "
                            f"(QTY: {updated_buy_order.qty}, NOTIONAL: {updated_buy_order.notional}) "
                            f"will stop being tracked due to status {updated_buy_order.status}."
                        )
                    # else: still open (NEW, ACCEPTED, PARTIALLY_FILLED, etc.) — do nothing
                except Exception as e:
                    self._logger.log_error(
                        f"Error updating buy order {entry['buy_order'].id}: {e}"
                    )

            # --- Sell order tracking ---
            if not entry['sell_order_terminal']:
                try:
                    updated_sell_order = self.trading_client.get_order_by_id(
                        entry['sell_order'].id
                    )
                    entry['sell_order'] = updated_sell_order

                    if updated_sell_order.status in self.TERMINAL_STATUSES:
                        entry['sell_order_terminal'] = True
                        if updated_sell_order.status == OrderStatus.FILLED:
                            self._logger.log_info(
                                f"Sell order for {updated_sell_order.symbol} "
                                f"(ID: {updated_sell_order.id}) fulfilled."
                            )
                        else:
                            self._logger.log_warning(
                                f"Sell order for {updated_sell_order.symbol} "
                                f"(ID: {updated_sell_order.id}) completed with status "
                                f"{updated_sell_order.status}."
                            )
                except Exception as e:
                    self._logger.log_error(
                        f"Error updating sell order {entry['sell_order'].id}: {e}"
                    )

    def check_ready_to_sell(self) -> List[Order]:
        """
        Get the list of buy orders whose hold period has elapsed and are ready to be sold.

        Returns:
            List[Order]: List of buy orders ready to be sold.
        """
        return self.ready_to_sell

    def clear_ready_to_sell(self) -> List[Order]:
        """
        Get and clear the ready-to-sell list.

        Returns:
            List[Order]: The list of buy orders that were ready to sell (now cleared).
        """
        temp = self.ready_to_sell
        self.ready_to_sell = []
        return temp

    def get_entry_by_article_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific archived entry by article ID.

        Args:
            article_id (str): Unique article identifier (link).

        Returns:
            Optional[Dict[str, Any]]: Archived entry dictionary or None if not found.
        """
        if article_id not in self._article_id_index:
            return None
        entry_index = self._article_id_index[article_id]
        return self.archived_entries[entry_index]

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """
        Retrieve all archived entries.

        Returns:
            List[Dict[str, Any]]: Copy of all archived entries.
        """
        return list(self.archived_entries)

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert all archived entries to a pandas DataFrame for analysis.

        The update() method should be called before to_dataframe() to ensure
        order data is current. No additional API calls are made by this method.

        Returns:
            pd.DataFrame: DataFrame with all archived entries and their details.
        """
        expected_columns = [
            'article_id', 'source_name', 'title', 'link', 'published_date', 'summary',
            'sentiment', 'ticker', 'format_match', 'ticker_found', 'raw_sentiment_response',
            'resulted_in_purchase', 'archived_at',
            'buy_order_id', 'buy_order_symbol', 'buy_order_qty', 'buy_order_status',
            'buy_order_filled_at', 'buy_order_filled_avg_price', 'buy_order_terminal',
            'sell_order_id', 'sell_order_symbol', 'sell_order_qty', 'sell_order_status',
            'sell_order_filled_at', 'sell_order_filled_avg_price', 'sell_order_terminal',
        ]

        if not self.archived_entries:
            return pd.DataFrame(columns=expected_columns)

        rows = []
        for entry in self.archived_entries:
            article_entry = entry['article_entry']
            sentiment = entry['sentiment_response']
            buy_order = entry['buy_order']
            sell_order = entry['sell_order']

            row = {
                'article_id': entry['article_id'],
                'source_name': entry['source_name'],
                'title': article_entry.get('title', None),
                'link': article_entry.get('link', None),
                'published_date': article_entry.get('published', None),
                'summary': article_entry.get('summary', None),
                'sentiment': sentiment.sentiment,
                'ticker': sentiment.ticker,
                'format_match': sentiment.format_match,
                'ticker_found': sentiment.ticker_found,
                'raw_sentiment_response': sentiment.raw_response,
                'resulted_in_purchase': entry['resulted_in_purchase'],
                'archived_at': entry['archived_at'],
                # Buy order fields
                'buy_order_id': str(buy_order.id) if buy_order else None,
                'buy_order_symbol': buy_order.symbol if buy_order else None,
                'buy_order_qty': float(buy_order.qty) if buy_order and buy_order.qty else None,
                'buy_order_status': str(buy_order.status) if buy_order else None,
                'buy_order_filled_at': buy_order.filled_at if buy_order else None,
                'buy_order_filled_avg_price': (
                    float(buy_order.filled_avg_price)
                    if buy_order and buy_order.filled_avg_price else None
                ),
                'buy_order_terminal': entry['buy_order_terminal'],
                # Sell order fields
                'sell_order_id': str(sell_order.id) if sell_order else None,
                'sell_order_symbol': sell_order.symbol if sell_order else None,
                'sell_order_qty': float(sell_order.qty) if sell_order and sell_order.qty else None,
                'sell_order_status': str(sell_order.status) if sell_order else None,
                'sell_order_filled_at': sell_order.filled_at if sell_order else None,
                'sell_order_filled_avg_price': (
                    float(sell_order.filled_avg_price)
                    if sell_order and sell_order.filled_avg_price else None
                ),
                'sell_order_terminal': entry['sell_order_terminal'],
            }
            rows.append(row)

        return pd.DataFrame(rows)
