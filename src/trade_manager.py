from datetime import datetime, timezone
from src.base.singleton import SingletonMeta
from src.base.sentiment_response import SentimentResponse
from src.base.tl_logger import LoggingService
from src.base.alpaca_client import AlpacaClient
from src.configs import MARKET_HOLD_TIME
from src.base.datetime_utils import ensure_utc, naive_local_to_utc
from src.database.db_service import DatabaseService
from alpaca.trading.client import TradingClient
from alpaca.trading.models import Order
from alpaca.trading.enums import OrderStatus
import pandas as pd
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass

@dataclass(frozen=True)
class PendingBuy:
    sentiment_id: int
    ticker: str
    article_id: str

@dataclass(frozen=True)
class PendingSell:
    buy_id: str
    ticker: str
    bought_at: datetime
    qty: int
# _MIGRATION_HINT = (
#     "Run scripts/migrate_trade_lifecycle_snapshot.py on persistent_data/trade_lifecycle.snapshot "
#     "(see project docs)."
# )


# def _validate_entry_shape(entry: Dict[str, Any], index: int) -> None:
#     if "buy_order" in entry or "sell_order" in entry:
#         raise ValueError(
#             f"Trade snapshot entry {index} uses legacy buy_order/sell_order fields. {_MIGRATION_HINT}"
#         )
#     if "buy_orders" not in entry:
#         raise ValueError(
#             f"Trade snapshot entry {index} missing 'buy_orders'. {_MIGRATION_HINT}"
#         )
#     if not isinstance(entry["buy_orders"], dict):
#         raise ValueError(f"Trade snapshot entry {index}: buy_orders must be a dict.")
#     if "sell_orders" not in entry or not isinstance(entry["sell_orders"], dict):
#         raise ValueError(f"Trade snapshot entry {index}: sell_orders must be a dict.")
#     if set(entry["sell_orders"].keys()) != set(entry["buy_orders"].keys()):
#         raise ValueError(
#             f"Trade snapshot entry {index}: sell_orders keys must match buy_orders keys."
#         )
#     if "buy_order_terminal" not in entry or not isinstance(entry["buy_order_terminal"], dict):
#         raise ValueError(f"Trade snapshot entry {index}: buy_order_terminal must be a dict.")
#     if "sell_order_terminal" not in entry or not isinstance(entry["sell_order_terminal"], dict):
#         raise ValueError(f"Trade snapshot entry {index}: sell_order_terminal must be a dict.")


class TradeManager(metaclass=SingletonMeta):
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
        self._db_service = DatabaseService()
        self.alpaca_client = AlpacaClient()
        self.trading_client: TradingClient = self.alpaca_client.trading_client
        self.archived_entries: List[Dict[str, Any]] = []
        self._article_id_index: Dict[str, int] = {}
        self._buy_order_id_index: Dict[str, str] = {}
        self.ready_to_sell: List[Order] = []

    def get_pending_buys(self) -> list[PendingBuy]:
        """
        Get a list of the purchases that need to be made.
        """
        rows = self._db_service.fetch_all(
            """
            SELECT s.id, s.ticker, s.article_id
            FROM sentiments s
            LEFT JOIN buy_orders b ON s.id = b.sentiment_id
            WHERE s.sentiment = 'positive'
            AND s.ticker_valid = TRUE
            AND b.sentiment_id IS NULL
            """
        )

        unique_article_ids = set([row[2] for row in rows])
        self._db_service.execute(
            """
            UPDATE articles
            SET resulted_in_purchase = %s
            WHERE article_id IN %s
            """,
            (
                True,
                tuple(unique_article_ids)
            ),
        )

        return [
            PendingBuy(sentiment_id=row[0], ticker=row[1], article_id=row[2])
            for row in rows
        ]

    def archive_buy(self, buys: list[PendingBuy], orders: list[Order]):
        """
        Create rows in the buy_orders table for new purchases
        """
        for buy, order in zip(buys, orders):
            if order is None:
                self._logger.log_warning(f"No order returned for Sentiment: {buy.sentiment_id}, Article: {buy.article_id}")
                continue
            
            data_dict = {
                "article_id": buy.article_id,
                "sentiment_id": buy.sentiment_id,
                "is_terminal": order.status in self.TERMINAL_STATUSES,
                "alpaca_order_id": order.id,
                "client_order_id": order.client_order_id,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "submitted_at": order.submitted_at,
                "filled_at": order.filled_at,
                "expired_at": order.expired_at,
                "expires_at": order.expires_at,
                "canceled_at": order.canceled_at,
                "failed_at": order.failed_at,
                "replaced_at": order.replaced_at,
                "replaced_by": order.replaced_by,
                "replaces": order.replaces,
                "asset_id": order.asset_id,
                "symbol": order.symbol,
                "asset_class": None if order.asset_class is None else order.asset_class.value,
                "notional": order.notional,
                "qty": order.qty,
                "filled_qty": order.filled_qty,
                "filled_avg_price": order.filled_avg_price,
                "order_class": None if order.order_class is None else order.order_class.value,
                "order_type": None if order.order_type is None else order.order_type.value,
                "type": None if order.type is None else order.type.value,
                "side": None if order.side is None else order.side.value,
                "time_in_force": None if order.time_in_force is None else order.time_in_force.value,
                "limit_price": order.limit_price,
                "stop_price": order.stop_price,
                "status": order.status.value,
                "extended_hours": order.extended_hours,
                "legs": order.legs,
                "trail_percent": order.trail_percent,
                "trail_price": order.trail_price,
                "hwm": order.hwm,
                "position_intent": None if order.position_intent is None else order.position_intent.value,
                "ratio_qty": order.ratio_qty,
            }
            
            self._db_service.insert_row_dict(
                "buy_orders",
                data_dict,
            )

    def _update_buy_orders(self):
        """
        Update the buy order if they aren't terminal.
        """
        rows = self._db_service.fetch_all(
            """
            SELECT alpaca_order_id FROM buy_orders
            WHERE is_terminal = FALSE
            """)
        non_terminal_buy_ids = [row[0] for row in rows]
        new_buy_orders = []
        for id in non_terminal_buy_ids:
            try:
                new_buy_orders.append(self.trading_client.get_order_by_id(id))
            except Exception as e:
                self._logger.log_error(f"Failed to update order id: {id} with error {e}")
                new_buy_orders.append(None)
        
        for order in new_buy_orders:
            if order is None:
                continue
            self._db_service.execute(
                """
                UPDATE buy_orders
                SET is_terminal = %s,
                    client_order_id = %s,
                    created_at = %s,
                    updated_at = %s,
                    submitted_at = %s,
                    filled_at = %s,
                    expired_at = %s,
                    expires_at = %s,
                    canceled_at = %s,
                    failed_at = %s,
                    replaced_at = %s,
                    replaced_by = %s,
                    replaces = %s,
                    asset_id = %s,
                    symbol = %s,
                    asset_class = %s,
                    notional = %s,
                    qty = %s,
                    filled_qty = %s,
                    filled_avg_price = %s,
                    order_class = %s,
                    order_type = %s,
                    "type" = %s,
                    side = %s,
                    time_in_force = %s,
                    limit_price = %s,
                    stop_price = %s,
                    status = %s,
                    extended_hours = %s,
                    legs = %s,
                    trail_percent = %s,
                    trail_price = %s,
                    hwm = %s,
                    position_intent = %s,
                    ratio_qty = %s
                WHERE alpaca_order_id = %s
                """,
                (
                    order.status in self.TERMINAL_STATUSES,
                    order.client_order_id,
                    order.created_at,
                    order.updated_at,
                    order.submitted_at,
                    order.filled_at,
                    order.expired_at,
                    order.expires_at,
                    order.canceled_at,
                    order.failed_at,
                    order.replaced_at,
                    order.replaced_by,
                    order.replaces,
                    order.asset_id,
                    order.symbol,
                    None if order.asset_class is None else order.asset_class.value,
                    order.notional,
                    order.qty,
                    order.filled_qty,
                    order.filled_avg_price,
                    None if order.order_class is None else order.order_class.value,
                    None if order.order_type is None else order.order_type.value,
                    None if order.type is None else order.type.value,
                    None if order.side is None else order.side.value,
                    None if order.time_in_force is None else order.time_in_force.value,
                    order.limit_price,
                    order.stop_price,
                    order.status.value,
                    order.extended_hours,
                    order.legs,
                    order.trail_percent,
                    order.trail_price,
                    order.hwm,
                    None if order.position_intent is None else order.position_intent.value,
                    order.ratio_qty,
                    order.id,
                ),
            )

    def _update_sell_orders(self):
        """
        Update the sell orders if they aren't terminal.
        """
        rows = self._db_service.fetch_all(
            """
            SELECT alpaca_order_id FROM sell_orders
            WHERE is_terminal = FALSE
            """
            )
        non_terminal_sell_ids = [row[0] for row in rows]
        new_sell_orders = []
        for id in non_terminal_sell_ids:
            try:
                new_sell_orders.append(self.trading_client.get_order_by_id(id))
            except Exception as e:
                self._logger.log_error(f"Failed to update order id: {id} with error {e}")
                new_sell_orders.append(None)
        
        for order in new_sell_orders:
            if order is None:
                continue
            self._db_service.execute(
                """
                UPDATE sell_orders
                SET is_terminal = %s,
                    client_order_id = %s,
                    created_at = %s,
                    updated_at = %s,
                    submitted_at = %s,
                    filled_at = %s,
                    expired_at = %s,
                    expires_at = %s,
                    canceled_at = %s,
                    failed_at = %s,
                    replaced_at = %s,
                    replaced_by = %s,
                    replaces = %s,
                    asset_id = %s,
                    symbol = %s,
                    asset_class = %s,
                    notional = %s,
                    qty = %s,
                    filled_qty = %s,
                    filled_avg_price = %s,
                    order_class = %s,
                    order_type = %s,
                    "type" = %s,
                    side = %s,
                    time_in_force = %s,
                    limit_price = %s,
                    stop_price = %s,
                    status = %s,
                    extended_hours = %s,
                    legs = %s,
                    trail_percent = %s,
                    trail_price = %s,
                    hwm = %s,
                    position_intent = %s,
                    ratio_qty = %s
                WHERE alpaca_order_id = %s
                """,
                (
                    order.status in self.TERMINAL_STATUSES,
                    order.client_order_id,
                    order.created_at,
                    order.updated_at,
                    order.submitted_at,
                    order.filled_at,
                    order.expired_at,
                    order.expires_at,
                    order.canceled_at,
                    order.failed_at,
                    order.replaced_at,
                    order.replaced_by,
                    order.replaces,
                    order.asset_id,
                    order.symbol,
                    None if order.asset_class is None else order.asset_class.value,
                    order.notional,
                    order.qty,
                    order.filled_qty,
                    order.filled_avg_price,
                    None if order.order_class is None else order.order_class.value,
                    None if order.order_type is None else order.order_type.value,
                    None if order.type is None else order.type.value,
                    None if order.side is None else order.side.value,
                    None if order.time_in_force is None else order.time_in_force.value,
                    order.limit_price,
                    order.stop_price,
                    order.status.value,
                    order.extended_hours,
                    order.legs,
                    order.trail_percent,
                    order.trail_price,
                    order.hwm,
                    None if order.position_intent is None else order.position_intent.value,
                    order.ratio_qty,
                    order.id,
                ),
            )

    def update(self):
        """
        Check each of the buy and sell orders that are not terminal and update their status.
        """
        self._update_buy_orders()
        self._update_sell_orders()

    def query_ready_to_sell(self) -> List[PendingSell]:
        """
        Check for purchase order that are ready to sell.

        Returns
        ---

        rows: List[tuple] - the database rows that are ready to sell
        """
        rows = self._db_service.fetch_all(
            """
            SELECT bo.alpaca_order_id, bo.symbol, bo.filled_at, bo.qty from buy_orders bo
            LEFT JOIN sell_orders so ON bo.alpaca_order_id = so.buy_order_id
            WHERE bo.status = 'filled'
            AND bo.filled_at <= %s
            AND so.buy_order_id IS NULL
            """,
            (datetime.now(timezone.utc) - MARKET_HOLD_TIME,)
        )
        return [PendingSell(row[0], row[1], row[2], row[3]) for row in rows]

    def archive_sell(self, buy_orders: list[PendingSell], sell_orders: list[Order]):
        """
        Create rows in the sell_orders table for new sell orders.
        """
        for buy, order in zip(buy_orders, sell_orders):
            if order is None:
                self._logger.log_warning(
                    f"No sell order returned for buy: {buy.buy_id}, ticker: {buy.ticker}"
                )
                continue

            data_dict = {
                "buy_order_id": buy.buy_id,
                "is_terminal": order.status in self.TERMINAL_STATUSES,
                "alpaca_order_id": order.id,
                "client_order_id": order.client_order_id,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "submitted_at": order.submitted_at,
                "filled_at": order.filled_at,
                "expired_at": order.expired_at,
                "expires_at": order.expires_at,
                "canceled_at": order.canceled_at,
                "failed_at": order.failed_at,
                "replaced_at": order.replaced_at,
                "replaced_by": order.replaced_by,
                "replaces": order.replaces,
                "asset_id": order.asset_id,
                "symbol": order.symbol,
                "asset_class": None if order.asset_class is None else order.asset_class.value,
                "notional": order.notional,
                "qty": order.qty,
                "filled_qty": order.filled_qty,
                "filled_avg_price": order.filled_avg_price,
                "order_class": None if order.order_class is None else order.order_class.value,
                "order_type": None if order.order_type is None else order.order_type.value,
                "type": None if order.type is None else order.type.value,
                "side": None if order.side is None else order.side.value,
                "time_in_force": None if order.time_in_force is None else order.time_in_force.value,
                "limit_price": order.limit_price,
                "stop_price": order.stop_price,
                "status": order.status.value,
                "extended_hours": order.extended_hours,
                "legs": order.legs,
                "trail_percent": order.trail_percent,
                "trail_price": order.trail_price,
                "hwm": order.hwm,
                "position_intent": None if order.position_intent is None else order.position_intent.value,
                "ratio_qty": order.ratio_qty,
            }

            self._db_service.insert_row_dict("sell_orders", data_dict)

    # def get_persistent_snapshot(self) -> Dict[str, Any]:
    #     """Return in-memory state to be persisted across restarts."""
    #     return {
    #         'archived_entries': self.archived_entries,
    #         '_article_id_index': self._article_id_index,
    #         '_buy_order_id_index': self._buy_order_id_index,
    #         'ready_to_sell': self.ready_to_sell,
    #     }

    # def restore_from_persistent_snapshot(self, snapshot: Dict[str, Any]) -> None:
    #     """Restore state from :meth:`get_persistent_snapshot`."""
    #     required = ('archived_entries', '_article_id_index', '_buy_order_id_index', 'ready_to_sell')
    #     for key in required:
    #         if key not in snapshot:
    #             raise ValueError(f"Invalid persistent snapshot: missing '{key}'")
    #     self.archived_entries = snapshot['archived_entries']
    #     self._article_id_index = snapshot['_article_id_index']
    #     self._buy_order_id_index = snapshot['_buy_order_id_index']
    #     self.ready_to_sell = snapshot['ready_to_sell']
    #     for i, entry in enumerate(self.archived_entries):
    #         _validate_entry_shape(entry, i)
    #     for entry in self.archived_entries:
    #         at = entry.get("archived_at")
    #         if isinstance(at, datetime) and at.tzinfo is None:
    #             entry["archived_at"] = naive_local_to_utc(at)
    #         elif isinstance(at, datetime):
    #             entry["archived_at"] = at.astimezone(timezone.utc)

    # def archive_news_entry(
    #     self,
    #     source_name: str,
    #     article_entry,
    #     sentiment_response: SentimentResponse,
    #     buy_orders: Optional[Dict[str, Order]] = None,
    #     sell_orders: Optional[Dict[str, Optional[Order]]] = None,
    # ) -> bool:
    #     """
    #     Archive a news article with its sentiment analysis and optional buy orders (per ticker).

    #     Args:
    #         source_name (str): Name of the RSS feed source.
    #         article_entry: Complete RSS feed entry from feedparser (FeedParserDict).
    #         sentiment_response (SentimentResponse): Sentiment analysis result.
    #         buy_orders: Ticker -> buy Order for successful buys (empty if none).
    #         sell_orders: Same keys as buy_orders; values None until a sell is logged.
    #     """
    #     buy_orders = dict(buy_orders) if buy_orders else {}
    #     sell_orders = dict(sell_orders) if sell_orders else {}

    #     if set(sell_orders.keys()) != set(buy_orders.keys()):
    #         self._logger.log_error(
    #             "archive_news_entry: sell_orders keys must match buy_orders keys."
    #         )
    #         return False

    #     article_id = article_entry.get('link')
    #     if article_id is None or article_id == '':
    #         self._logger.log_error(
    #             f"Cannot archive entry from {source_name}: missing 'link' field in article_entry."
    #         )
    #         return False

    #     if article_id in self._article_id_index:
    #         self._logger.log_warning(
    #             f"Duplicate article_id '{article_id}' — entry already archived. Skipping."
    #         )
    #         return False

    #     buy_order_terminal = {sym: False for sym in buy_orders}
    #     sell_order_terminal = {sym: True for sym in buy_orders}

    #     entry = {
    #         'article_id': article_id,
    #         'source_name': source_name,
    #         'article_entry': article_entry,
    #         'sentiment_response': sentiment_response,
    #         'buy_orders': buy_orders,
    #         'sell_orders': sell_orders,
    #         'archived_at': datetime.now(timezone.utc),
    #         'resulted_in_purchase': len(buy_orders) > 0,
    #         'buy_order_terminal': buy_order_terminal,
    #         'sell_order_terminal': sell_order_terminal,
    #     }

    #     self.archived_entries.append(entry)
    #     self._article_id_index[article_id] = len(self.archived_entries) - 1

    #     for bo in buy_orders.values():
    #         self._buy_order_id_index[str(bo.id)] = article_id

    #     self._logger.log_info(
    #         f"Archived entry from {source_name}: '{article_entry.get('title', 'N/A')}' "
    #         f"(purchases={len(buy_orders)})"
    #     )
    #     return True

    # def log_sell_order(self, buy_order: Order, sell_order: Order) -> bool:
    #     """Log a sell order against the archive entry for that buy's ticker."""
    #     buy_order_id_str = str(buy_order.id)

    #     article_id = self._buy_order_id_index.get(buy_order_id_str)
    #     if article_id is None:
    #         self._logger.log_error(
    #             f"Cannot log sell order: buy order ID '{buy_order_id_str}' not found in archive."
    #         )
    #         return False

    #     entry_index = self._article_id_index[article_id]
    #     entry = self.archived_entries[entry_index]

    #     sym = None
    #     for k, bo in entry['buy_orders'].items():
    #         if bo.id == buy_order.id:
    #             sym = k
    #             break
    #     if sym is None:
    #         self._logger.log_error(
    #             f"Cannot log sell order: buy order ID '{buy_order_id_str}' not in entry buy_orders."
    #         )
    #         return False

    #     prev = entry['sell_orders'].get(sym)
    #     if prev is not None:
    #         self._logger.log_warning(
    #             f"Overwriting existing sell order for article '{article_id}' symbol {sym} "
    #             f"(old sell order ID: {prev.id})."
    #         )

    #     entry['sell_orders'][sym] = sell_order
    #     entry['sell_order_terminal'][sym] = False

    #     self._logger.log_info(
    #         f"Logged sell order {sell_order.id} for {sell_order.symbol} "
    #         f"against buy order {buy_order_id_str}."
    #     )
    #     return True

    # def update(self) -> None:
    #     """Refresh order state from Alpaca; move filled buys past hold into ready_to_sell."""
    #     for entry in self.archived_entries:
    #         for sym, buy in list(entry['buy_orders'].items()):
    #             if entry['buy_order_terminal'].get(sym, True):
    #                 continue
    #             try:
    #                 updated_buy_order = self.trading_client.get_order_by_id(buy.id)
    #                 entry['buy_orders'][sym] = updated_buy_order

    #                 if updated_buy_order.status == OrderStatus.FILLED:
    #                     filled_utc = ensure_utc(updated_buy_order.filled_at)
    #                     if filled_utc is not None:
    #                         sell_time = filled_utc + MARKET_HOLD_TIME
    #                         if datetime.now(timezone.utc) >= sell_time:
    #                             self.ready_to_sell.append(updated_buy_order)
    #                             entry['buy_order_terminal'][sym] = True
    #                             self._logger.log_info(
    #                                 f"Buy order for {updated_buy_order.symbol} (ID: {updated_buy_order.id}) "
    #                                 f"filled and hold period elapsed. Added to ready_to_sell."
    #                             )
    #                 elif updated_buy_order.status in (
    #                     OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED
    #                 ):
    #                     entry['buy_order_terminal'][sym] = True
    #                     self._logger.log_warning(
    #                         f"Buy order for {updated_buy_order.symbol} "
    #                         f"(QTY: {updated_buy_order.qty}, NOTIONAL: {updated_buy_order.notional}) "
    #                         f"will stop being tracked due to status {updated_buy_order.status}."
    #                     )
    #             except Exception as e:
    #                 self._logger.log_error(
    #                     f"Error updating buy order {buy.id}: {e}"
    #                 )

    #         for sym, sell in list(entry['sell_orders'].items()):
    #             if sell is None:
    #                 continue
    #             if entry['sell_order_terminal'].get(sym, True):
    #                 continue
    #             try:
    #                 updated_sell_order = self.trading_client.get_order_by_id(sell.id)
    #                 entry['sell_orders'][sym] = updated_sell_order

    #                 if updated_sell_order.status in self.TERMINAL_STATUSES:
    #                     entry['sell_order_terminal'][sym] = True
    #                     if updated_sell_order.status == OrderStatus.FILLED:
    #                         self._logger.log_info(
    #                             f"Sell order for {updated_sell_order.symbol} "
    #                             f"(ID: {updated_sell_order.id}) fulfilled."
    #                         )
    #                     else:
    #                         self._logger.log_warning(
    #                             f"Sell order for {updated_sell_order.symbol} "
    #                             f"(ID: {updated_sell_order.id}) completed with status "
    #                             f"{updated_sell_order.status}."
    #                         )
    #             except Exception as e:
    #                 self._logger.log_error(
    #                     f"Error updating sell order {sell.id}: {e}"
    #                 )

    # def check_ready_to_sell(self) -> List[Order]:
    #     """Buy orders whose hold period has elapsed."""
    #     return self.ready_to_sell

    # def clear_ready_to_sell(self) -> List[Order]:
    #     temp = self.ready_to_sell
    #     self.ready_to_sell = []
    #     return temp

    # def get_entry_by_article_id(self, article_id: str) -> Optional[Dict[str, Any]]:
    #     if article_id not in self._article_id_index:
    #         return None
    #     entry_index = self._article_id_index[article_id]
    #     return self.archived_entries[entry_index]

    # def get_all_entries(self) -> List[Dict[str, Any]]:
    #     return list(self.archived_entries)

    # def _row_for_symbol(
    #     self,
    #     entry: Dict[str, Any],
    #     article_entry: Any,
    #     sentiment: SentimentResponse,
    #     sym: str,
    # ) -> Dict[str, Any]:
    #     buy_order = entry['buy_orders'].get(sym)
    #     sell_order = entry['sell_orders'].get(sym)
    #     has_buy = buy_order is not None
    #     buy_term = entry['buy_order_terminal'].get(sym, True)
    #     sell_term = entry['sell_order_terminal'].get(sym, True)

    #     return {
    #         'article_id': entry['article_id'],
    #         'source_name': entry['source_name'],
    #         'title': article_entry.get('title', None),
    #         'link': article_entry.get('link', None),
    #         'published_date': article_entry.get('published', None),
    #         'summary': article_entry.get('summary', None),
    #         'sentiment': sentiment.sentiment,
    #         'ticker': sym,
    #         'format_match': sentiment.format_match,
    #         'ticker_found': sentiment.ticker_found,
    #         'raw_sentiment_response': sentiment.raw_response,
    #         'resulted_in_purchase': entry['resulted_in_purchase'],
    #         'has_buy_order': has_buy,
    #         'archived_at': entry['archived_at'],
    #         'buy_order_id': str(buy_order.id) if buy_order else None,
    #         'buy_order_symbol': buy_order.symbol if buy_order else None,
    #         'buy_order_qty': float(buy_order.qty) if buy_order and buy_order.qty else None,
    #         'buy_order_status': str(buy_order.status) if buy_order else None,
    #         'buy_order_filled_at': buy_order.filled_at if buy_order else None,
    #         'buy_order_filled_avg_price': (
    #             float(buy_order.filled_avg_price)
    #             if buy_order and buy_order.filled_avg_price else None
    #         ),
    #         'buy_order_terminal': buy_term if has_buy else True,
    #         'sell_order_id': str(sell_order.id) if sell_order else None,
    #         'sell_order_symbol': sell_order.symbol if sell_order else None,
    #         'sell_order_qty': float(sell_order.qty) if sell_order and sell_order.qty else None,
    #         'sell_order_status': str(sell_order.status) if sell_order else None,
    #         'sell_order_filled_at': sell_order.filled_at if sell_order else None,
    #         'sell_order_filled_avg_price': (
    #             float(sell_order.filled_avg_price)
    #             if sell_order and sell_order.filled_avg_price else None
    #         ),
    #         'sell_order_terminal': sell_term if sell_order else True,
    #     }

    # def _row_without_ticker(
    #     self,
    #     entry: Dict[str, Any],
    #     article_entry: Any,
    #     sentiment: SentimentResponse,
    # ) -> Dict[str, Any]:
    #     """Single table row when sentiment has no symbols (e.g. ticker NONE)."""
    #     # Normal flow: no tickers => empty buy_orders; non-empty buys with empty ticker list would not show here.
    #     return {
    #         'article_id': entry['article_id'],
    #         'source_name': entry['source_name'],
    #         'title': article_entry.get('title', None),
    #         'link': article_entry.get('link', None),
    #         'published_date': article_entry.get('published', None),
    #         'summary': article_entry.get('summary', None),
    #         'sentiment': sentiment.sentiment,
    #         'ticker': None,
    #         'format_match': sentiment.format_match,
    #         'ticker_found': sentiment.ticker_found,
    #         'raw_sentiment_response': sentiment.raw_response,
    #         'resulted_in_purchase': entry['resulted_in_purchase'],
    #         'has_buy_order': False,
    #         'archived_at': entry['archived_at'],
    #         'buy_order_id': None,
    #         'buy_order_symbol': None,
    #         'buy_order_qty': None,
    #         'buy_order_status': None,
    #         'buy_order_filled_at': None,
    #         'buy_order_filled_avg_price': None,
    #         'buy_order_terminal': True,
    #         'sell_order_id': None,
    #         'sell_order_symbol': None,
    #         'sell_order_qty': None,
    #         'sell_order_status': None,
    #         'sell_order_filled_at': None,
    #         'sell_order_filled_avg_price': None,
    #         'sell_order_terminal': True,
    #     }

    # def to_dataframe(self) -> pd.DataFrame:
    #     """
    #     One row per archived article: one row per sentiment symbol when present, otherwise
    #     one row with null ticker so headlines still appear in the UI.
    #     """
    #     expected_columns = [
    #         'article_id', 'source_name', 'title', 'link', 'published_date', 'summary',
    #         'sentiment', 'ticker', 'format_match', 'ticker_found', 'raw_sentiment_response',
    #         'resulted_in_purchase', 'has_buy_order', 'archived_at',
    #         'buy_order_id', 'buy_order_symbol', 'buy_order_qty', 'buy_order_status',
    #         'buy_order_filled_at', 'buy_order_filled_avg_price', 'buy_order_terminal',
    #         'sell_order_id', 'sell_order_symbol', 'sell_order_qty', 'sell_order_status',
    #         'sell_order_filled_at', 'sell_order_filled_avg_price', 'sell_order_terminal',
    #     ]

    #     if not self.archived_entries:
    #         return pd.DataFrame(columns=expected_columns)

    #     rows: List[Dict[str, Any]] = []
    #     for entry in self.archived_entries:
    #         article_entry = entry['article_entry']
    #         sentiment = entry['sentiment_response']
    #         symbols = sentiment.get_ticker_list()
    #         if not symbols:
    #             rows.append(self._row_without_ticker(entry, article_entry, sentiment))
    #         else:
    #             for sym in symbols:
    #                 rows.append(self._row_for_symbol(entry, article_entry, sentiment, sym))

    #     return pd.DataFrame(rows)
