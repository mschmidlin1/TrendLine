from datetime import datetime, timezone
from trend_core.base.singleton import SingletonMeta
from trend_core.base.tl_logger import LoggingService
from trend_core.base.alpaca_client import AlpacaClient
from trend_core.configs import MARKET_HOLD_TIME
from trend_core.base.datetime_utils import ensure_utc, naive_local_to_utc
from trend_core.database.db_service import DatabaseService
from alpaca.trading.client import TradingClient
from alpaca.trading.models import Order
from alpaca.trading.enums import OrderStatus
import pandas as pd
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from trend_core.trader import OrderAttempt
import json
from psycopg.types.json import Jsonb
from decimal import Decimal
@dataclass(frozen=True)
class PendingBuy:
    sentiment_id: int
    ticker: str
    article_id: str

@dataclass(frozen=True)
class PendingSell:
    trade_id: int
    ticker: str
    bought_at: datetime
    qty: Decimal


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

    def __init__(self) -> None:
        """Initialize the TradeLifecycleManager service."""
        self._logger = LoggingService()
        self._db_service = DatabaseService()
        self.alpaca_client = AlpacaClient()
        self.trading_client: TradingClient = self.alpaca_client.trading_client


    def _order_to_row(self, order: Order) -> dict[str, Any]:
        """Project an Alpaca Order onto the columns of the orders table."""
        def enum(v):
            return None if v is None else v.value
        return {
            "alpaca_order_id":  order.id,
            "side":             enum(order.side),
            "symbol":           order.symbol,
            "status":           enum(order.status),
            "client_order_id":  order.client_order_id,
            "asset_id":         order.asset_id,
            "asset_class":      enum(order.asset_class),
            "order_class":      enum(order.order_class),
            "order_type":       enum(order.order_type),
            "type":             enum(order.type),
            "time_in_force":    enum(order.time_in_force),
            "position_intent":  enum(order.position_intent),
            "qty":              order.qty,
            "notional":         order.notional,
            "filled_qty":       order.filled_qty,
            "filled_avg_price": order.filled_avg_price,
            "limit_price":      order.limit_price,
            "stop_price":       order.stop_price,
            "trail_percent":    order.trail_percent,
            "trail_price":      order.trail_price,
            "hwm":              order.hwm,
            "ratio_qty":        order.ratio_qty,
            "extended_hours":   order.extended_hours,
            "created_at":       order.created_at,
            "updated_at":       order.updated_at,
            "submitted_at":     order.submitted_at,
            "filled_at":        order.filled_at,
            "expired_at":       order.expired_at,
            "expires_at":       order.expires_at,
            "canceled_at":      order.canceled_at,
            "failed_at":        order.failed_at,
            "replaced_at":      order.replaced_at,
            "replaced_by":      order.replaced_by,
            "replaces":         order.replaces,
            "legs": None if order.legs is None
                    else Jsonb([json.loads(leg.model_dump_json()) for leg in order.legs]),
            "raw":  Jsonb(json.loads(order.model_dump_json())),
        }

    def get_pending_buys(self) -> list[PendingBuy]:
        """
        Get a list of the purchases that need to be made.
        """
        rows = self._db_service.fetch_all(
            """
            SELECT s.id, s.ticker, s.article_id
            FROM sentiments s
            LEFT JOIN trades t ON t.sentiment_id = s.id
            WHERE s.sentiment = 'positive'
            AND s.ticker_valid = TRUE
            AND t.sentiment_id IS NULL
            """
        )

        return [
            PendingBuy(sentiment_id=row[0], ticker=row[1], article_id=row[2])
            for row in rows
        ]

    def archive_buy(self, buys: list[PendingBuy], orders: list[OrderAttempt]):
        """
        Create rows in the trades and orders tables
        """
        for buy, attempt in zip(buys, orders):
            if attempt.order is not None:
                self._db_service.insert_row_dict("orders", self._order_to_row(attempt.order))
                self._db_service.insert_row_dict("trades", {
                    "sentiment_id": buy.sentiment_id,
                    "article_id": buy.article_id,
                    "symbol": buy.ticker,
                    "buy_order_id": attempt.order.id,
                })
            else:
                self._db_service.insert_row_dict("trades", {
                    "sentiment_id": buy.sentiment_id,
                    "article_id": buy.article_id,
                    "symbol": buy.ticker,
                    "buy_failure_reason": attempt.failure_reason,
                })

    def update(self):
        """
        Check each of the buy and sell orders that are not terminal and update their status.
        """
        rows = self._db_service.fetch_all(
            "SELECT alpaca_order_id FROM orders WHERE NOT is_terminal"
        )
        for (order_id,) in rows:
            try:
                order = self.trading_client.get_order_by_id(order_id)
            except Exception as e:
                self._logger.log_error(f"Failed to refresh order {order_id}: {e}")
                continue
            self._db_service.update_row_dict(
                "orders", self._order_to_row(order), key="alpaca_order_id"
            )

    def query_ready_to_sell(self) -> List[PendingSell]:
        """
        Check for purchase order that are ready to sell.

        Returns
        ---

        rows: List[tuple] - the database rows that are ready to sell
        """
        rows = self._db_service.fetch_all(
            """
            SELECT t.id, t.symbol, b.filled_at, b.filled_qty
            FROM trades t
            JOIN orders b ON b.alpaca_order_id = t.buy_order_id
            WHERE b.status = 'filled'
            AND b.filled_at <= %s
            AND t.sell_order_id IS NULL
            """,
            (datetime.now(timezone.utc) - MARKET_HOLD_TIME,)
        )
        return [PendingSell(row[0], row[1], row[2], row[3]) for row in rows]

    def archive_sell(self, sells: list[PendingSell], sell_orders: list[OrderAttempt]):
        """
        Create rows in the sell_orders table for new sell orders.
        """
        for sell, attempt in zip(sells, sell_orders):
            if attempt.order is not None:
                self._db_service.insert_row_dict("orders", self._order_to_row(attempt.order))
                self._db_service.execute(
                    """
                    UPDATE trades
                    SET sell_order_id = %s, sell_failure_reason = NULL, sell_attempted_at = now()
                    WHERE id = %s;
                    """,(
                        attempt.order.id,
                        sell.trade_id
                    ) 
                )
            else:
                self._db_service.execute(
                    """
                    UPDATE trades
                    SET sell_failure_reason = %s, sell_attempted_at = now()
                    WHERE id = %s;
                    """,(
                        attempt.failure_reason,
                        sell.trade_id
                    ) 
                )

    