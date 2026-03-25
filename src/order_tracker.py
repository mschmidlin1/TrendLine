from src.base.singleton import SingletonMeta
from src.base.alpaca_client import AlpacaClient
from alpaca.trading.client import TradingClient
from alpaca.trading.models import Order
import pandas as pd
from src.configs import MARKET_HOLD_TIME
from datetime import datetime
from uuid import UUID
from typing import List
from alpaca.trading.enums import OrderStatus
from src.base.tl_logger import LoggingService

class OrderTracker(metclass=SingletonMeta):
    """
    `log_purchase` - log a purchase that will sell after a fixed time

    `update` - updates the status of the class

    `clear_ready_to_sell` - gets and clears the ready to sell list

    `check_ready_to_sell` - gets the ready to sell list
    
    """
    def __init__(self):
        self.alpaca_client = AlpacaClient()
        self.trading_client: TradingClient = self.alpaca_client.trading_client
        self.tracked: List[Order] = []
        self.ready_to_sell: List[Order] = []
        self._logger = LoggingService()
    
    def update(self):
        """
        Updates the information in all of the tracked orders.
        """
        new_tracked = []
        for order in self.tracked:
            new_tracked.append(self.trading_client.get_order_by_id(order.id))
        self.tracked = new_tracked
        self._check_statuses()

    def log_purchase(self, order: Order):
        """
        Adds this order to the tracked list.
        """
        self.tracked.append(order)

    def _check_statuses(self):
        """
        This method checks the status of each id in the dataframe by querying the id with the trading client (self.trading_client.get_order_by_id(order_id)).

        If the status is closed and fulfilled, call `log_to_sell()`. This item can then be removed from the tracking df.

        If the status is closed and not fulfilled, just remove the order from the tracking df.

        If the status is still open, nothing happens to that row.
        """
        filtered_orders = []
        for order in self.tracked:
            if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED]:
                if order.status == OrderStatus.FILLED:
                    sell_time = order.filled_at + MARKET_HOLD_TIME
                    if sell_time > datetime.now():
                        self.ready_to_sell.append(order)
                    else:
                        filtered_orders.append(order)
                else:
                    self._logger.log_warning(f"Order for {order.symbol} with QTY {order.qty} and NOTIONAL {order.notional} will stop being tracked due to status {order.status}")
                    #do nothing here except log. The status is one of CANCELED, EXPIRED, REJECTED so we want to stop trackinng it
            else:
                #these orders are still open so they need to keep being tracked
                filtered_orders.append(order)
        self.tracked = filtered_orders

    def clear_ready_to_sell(self) -> List[Order]:
        """
        Gets all of the ready to sell orders.
        **Attention** This also clears the ready to sell list.
        """
        temp = self.ready_to_sell
        self.ready_to_sell = []
        return temp
    
    def check_ready_to_sell(self) -> List[Order]:
        """
        Gets all of the ready to sell orders.
        """
        return self.ready_to_sell
