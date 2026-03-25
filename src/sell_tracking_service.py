from src.base.singleton import SingletonMeta
from src.base.alpaca_client import AlpacaClient
from alpaca.trading.client import TradingClient
from alpaca.trading.models import Order
from alpaca.trading.enums import OrderStatus
from src.base.tl_logger import LoggingService
from datetime import datetime
from typing import List, Dict, Union


class SellTrackingService(metaclass=SingletonMeta):
    """
    Singleton service for tracking sell orders through their lifecycle.
    
    This service monitors sell orders after they are submitted to Alpaca,
    updating their status until they reach a terminal state (FILLED, CANCELED,
    EXPIRED, or REJECTED). All completed orders are stored for future database
    persistence.
    
    Attributes:
        alpaca_client (AlpacaClient): Singleton Alpaca client instance
        trading_client (TradingClient): Alpaca trading client for API calls
        tracked_sells (List[Dict[str, Union[Order, datetime]]]): Active sell orders being tracked
        fulfilled_sells (List[Dict[str, Union[Order, datetime]]]): Completed sells ready for DB storage
        _logger (LoggingService): Logging service instance
    """
    
    def __init__(self):
        """Initialize the SellTrackingService with required dependencies."""
        self.alpaca_client = AlpacaClient()
        self.trading_client: TradingClient = self.alpaca_client.trading_client
        self.tracked_sells: List[Dict[str, Union[Order, datetime]]] = []
        self.fulfilled_sells: List[Dict[str, Union[Order, datetime]]] = []
        self._logger = LoggingService()
        self._logger.log_debug("Instance of SellTrackingService() class created.")
    
    def log_sell(self, buy_order: Order, sell_order: Order) -> None:
        """
        Log a new sell order along with its corresponding buy order.
        
        Args:
            buy_order (Order): The original buy order object from Alpaca
            sell_order (Order): The sell order object from Alpaca
        """
        tracking_dict = {
            'buy_order': buy_order,
            'sell_order': sell_order,
            'logged_at': datetime.now()
        }
        self.tracked_sells.append(tracking_dict)
    
    def update(self) -> None:
        """
        Update the status of all tracked sell orders.
        
        Fetches the latest order status from Alpaca for each tracked sell order
        and processes any orders that have reached a terminal state.
        """
        new_tracked = []
        for order_dict in self.tracked_sells:
            # Fetch updated order status from Alpaca
            updated_sell_order = self.trading_client.get_order_by_id(order_dict['sell_order'].id)
            # Update the sell_order in the dictionary with fresh data
            order_dict['sell_order'] = updated_sell_order
            new_tracked.append(order_dict)
        
        self.tracked_sells = new_tracked
        self._check_statuses()
    
    def _check_statuses(self) -> None:
        """
        Check status of all tracked orders and move completed ones to fulfilled_sells.
        
        Orders with terminal statuses (FILLED, CANCELED, EXPIRED, REJECTED) are
        moved to fulfilled_sells. Orders still in progress continue to be tracked.
        """
        filtered_orders = []
        
        for order_dict in self.tracked_sells:
            sell_order = order_dict['sell_order']
            
            if sell_order.status == OrderStatus.FILLED:
                # Successfully filled order
                fulfilled_dict = {
                    'buy_order': order_dict['buy_order'],
                    'sell_order': sell_order,
                    'completed_at': datetime.now()
                }
                self.fulfilled_sells.append(fulfilled_dict)
                self._logger.log_info(f"Sell order fulfilled for {sell_order.symbol} (Qty: {sell_order.qty})")
                
            elif sell_order.status in [OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED]:
                # Order reached terminal state but was not filled
                fulfilled_dict = {
                    'buy_order': order_dict['buy_order'],
                    'sell_order': sell_order,
                    'completed_at': datetime.now()
                }
                self.fulfilled_sells.append(fulfilled_dict)
                self._logger.log_warning(f"Sell order for {sell_order.symbol} completed with status {sell_order.status}")
                
            else:
                # Order is still open (NEW, ACCEPTED, PARTIALLY_FILLED, etc.)
                filtered_orders.append(order_dict)
        
        self.tracked_sells = filtered_orders
