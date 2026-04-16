from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.trading.requests import GetAssetsRequest
from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest, CryptoLatestQuoteRequest
from alpaca.data.requests import CryptoBarsRequest
from alpaca.trading.models import Order, Position
from alpaca.data.timeframe import TimeFrame
from alpaca.data.models.quotes import Quote

import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout as RequestsTimeout

from src.configs import ALPACA_CHOSEN_SECRET_KEY
from src.base.tl_logger import LoggingService
from src.base.singleton import SingletonMeta
from src.base.alpaca_client import AlpacaClient
from src.ticker_service import TickerService
from src.converters import orders_to_dataframe
from src.account_service import AccountService

class Trader():
    """
    Base trader class for interacting with Alpaca trading API.
    
    Provides core functionality for trading operations including buying, selling,
    retrieving account information, positions, and orders. This class serves as
    the foundation for specialized traders (StockTrader, CryptoTrader).
    
    Attributes:
        API_ID (str): Alpaca API key ID.
        SECRET_KEY (str): Alpaca API secret key.
        trading_client (TradingClient): Alpaca trading client instance.
        logger (LoggingService): Logging service for tracking operations.
        timeframe_lookup (dict): Mapping of string timeframes to TimeFrame enums.
    """
    timeframe_lookup = {
        'day': TimeFrame.Day,
        'hour': TimeFrame.Hour,
        'minute': TimeFrame.Minute
    }
    def __init__(self, alpaca_client: AlpacaClient = AlpacaClient()) -> None:
        """
        Initialize the Trader instance.
        
        Args:
            API_ID (str): Alpaca API key ID.
            SECRET_KEY (str): Alpaca API secret key.
            paper (bool, optional): Whether to use paper trading. Defaults to True.
        """
        self.alpaca_client: AlpacaClient = alpaca_client
        self.trading_client = self.alpaca_client.trading_client
        self._logger = LoggingService()
        self.ticker_service = TickerService()
        self.account_service = AccountService()
    

    
    def get_ask_price(self, symbol: str) -> float:
        """
        Get the current ask price for a given symbol.
        
        Args:
            symbol (str): The trading symbol to query.
            
        Returns:
            float: The current ask price for the symbol.
        """
        quote = self.get_quote(symbol)
        return quote.ask_price

    def get_bid_price(self, symbol: str) -> float:
        """
        Get the current bid price for a given symbol.
        
        Args:
            symbol (str): The trading symbol to query.
            
        Returns:
            float: The current bid price for the symbol.
        """
        quote = self.get_quote(symbol)
        return quote.bid_price
    
    def get_orders(self, filter_status: QueryOrderStatus = QueryOrderStatus.ALL) -> List[Order]:
        """
        Retrieve orders filtered by status and return as a pandas DataFrame.
        
        Args:
            filter_status (QueryOrderStatus, optional): Filter for order status. Options include:
                - QueryOrderStatus.OPEN: Only open orders (new, accepted, partially_filled)
                - QueryOrderStatus.CLOSED: Only closed orders (filled, canceled, expired, rejected)
                - QueryOrderStatus.ALL: All orders regardless of status
                Defaults to QueryOrderStatus.ALL.
        
        Returns:
            pd.DataFrame: DataFrame containing order data with the following columns:
                - id: Order ID (str)
                - client_order_id: Client-assigned order ID (str)
                - created_at: Order creation timestamp (datetime)
                - updated_at: Last update timestamp (datetime)
                - submitted_at: Submission timestamp (datetime)
                - filled_at: Fill timestamp (datetime or None)
                - expired_at: Expiration timestamp (datetime or None)
                - canceled_at: Cancellation timestamp (datetime or None)
                - failed_at: Failure timestamp (datetime or None)
                - replaced_at: Replacement timestamp (datetime or None)
                - replaced_by: ID of replacing order (str or None)
                - replaces: ID of replaced order (str or None)
                - asset_id: Asset UUID (str)
                - symbol: Trading symbol (str)
                - asset_class: Asset class (str)
                - notional: Dollar amount for notional orders (float or None)
                - qty: Quantity ordered (float or None)
                - filled_qty: Quantity filled (float)
                - filled_avg_price: Average fill price (float or None)
                - order_class: Order class (str)
                - order_type: Order type (str)
                - type: Order type (str)
                - side: Order side (str)
                - time_in_force: Time in force (str)
                - limit_price: Limit price (float or None)
                - stop_price: Stop price (float or None)
                - status: Order status (str)
                - extended_hours: Extended hours flag (bool)
                - legs: Legs for multi-leg orders (list or None)
                - trail_percent: Trail percent (float or None)
                - trail_price: Trail price (float or None)
                - hwm: High water mark (float or None)
                
            Returns an empty DataFrame with no columns if no orders match the filter.
        """
        request = GetOrdersRequest(status=filter_status)
        all_orders: List[Order] = self.trading_client.get_orders(filter=request)
        return all_orders
        

    def get_orders_open(self) -> List[Order]:
        """
        Get all the open orders.
        """
        return self.get_orders(QueryOrderStatus.OPEN)
    
    def get_orders_closed(self) -> List[Order]:
        """
        Get all the closed orders.
        """
        return self.get_orders(QueryOrderStatus.CLOSED)

    def buy(self, symbol: str, quantity: Optional[float] = None, price: Optional[float] = None,
            side: OrderSide = OrderSide.BUY, time_in_force: TimeInForce = TimeInForce.GTC) -> Order | None:
        """
        Execute a buy order for the specified symbol.
        
        Must choose either to buy a `quantity` of shares or buy a specific amount in terms of
        `price`. Both should be float or int arguments.
        
        Args:
            symbol (str): The trading symbol to buy.
            quantity (Optional[float], optional): Number of shares/units to buy. Defaults to None.
            price (Optional[float], optional): Dollar amount to spend on the purchase. Defaults to None.
            side (OrderSide, optional): Order side (should be BUY). Defaults to OrderSide.BUY.
            time_in_force (TimeInForce, optional): Order time in force. Defaults to TimeInForce.GTC.
            
        Returns:
            int: `alpaca.trading.models.Order` or `None` if no trade was submitted
            
        Raises:
            ValueError: If symbol is not available or if both/neither quantity and price are specified.
        """
        #check function imputs
        if (quantity is None and price is None) or (quantity!=None and price!=None):
            raise ValueError("Must specify either quantity or price.")

        if not self.ticker_service.is_tradable_stock_symbol(symbol):
            self._logger.log_warning(f"Symbol '{symbol}' is not active/tradable on Alpaca. Skipping buy.")
            return None

        #check to make sure you have enough buying power
        try:
            if price==None:
                price = self.get_ask_price(symbol)*quantity
        except KeyError as e:
            self._logger.log_warning(f"Could not get quote for Symbol {symbol}. Abandoning stock buy.")
            return None
        try:
            buying_power = self.account_service.get_buying_power()
        except RequestsConnectionError as e:
            self._logger.log_warning(
                f"Connection error while fetching buying power for buy of '{symbol}'. Skipping. Error: {e}"
            )
            return None
        except RequestsTimeout as e:
            self._logger.log_warning(
                f"Timeout while fetching buying power for buy of '{symbol}'. Skipping. Error: {e}"
            )
            return None
        if price>buying_power:
            self._logger.log_warning(f"Not enough funds to buy {price} of '{symbol}'. Buying power is {buying_power}")
            return None
        elif quantity is None:
            self._logger.log_info(f"Buying {price} dollars of {symbol}.")
            market_order_data = MarketOrderRequest(
                                symbol=symbol,
                                notional=price,
                                side=side,
                                time_in_force=time_in_force
                            )
        else:
            self._logger.log_info(f"Buying {quantity} shares of {symbol}.")
            market_order_data = MarketOrderRequest(
                                symbol=symbol,
                                qty=quantity,
                                side=side,
                                time_in_force=time_in_force
                            )
        try:
            market_order: Order = self.trading_client.submit_order(market_order_data)
        except APIError as e:
            self._logger.log_warning(f"Alpaca rejected buy for '{symbol}'. Skipping. Error: {e}")
            return None
        except RequestsConnectionError as e:
            self._logger.log_warning(f"Connection error placing buy for '{symbol}'. Skipping. Error: {e}")
            return None
        except RequestsTimeout as e:
            self._logger.log_warning(f"Timeout placing buy for '{symbol}'. Skipping. Error: {e}")
            return None

        return market_order

    def sell_all(self, cancel_orders: bool = True) -> None:
        """
        Close all open positions.
        
        Args:
            cancel_orders (bool, optional): Whether to cancel all open orders. Defaults to True.
        """
        self.trading_client.close_all_positions(cancel_orders=cancel_orders)

    def sell(self, symbol: str, quantity: Optional[float] = None, price: Optional[float] = None,
             side: OrderSide = OrderSide.SELL, time_in_force: TimeInForce = TimeInForce.GTC) -> Order:
        """
        Execute a sell order for the specified symbol.
        
        Must choose either to *sell* a `quantity` or sell a specific amount in terms of
        `price`. Both should be float or int arguments.
        
        Args:
            symbol (str): The trading symbol to sell.
            quantity (Optional[float], optional): Number of shares/units to sell. Defaults to None.
            price (Optional[float], optional): Dollar amount worth of the asset to sell. Defaults to None.
            side (OrderSide, optional): Order side (should be SELL). Defaults to OrderSide.SELL.
            time_in_force (TimeInForce, optional): Order time in force. Defaults to TimeInForce.GTC.
            
        Returns:
            Order: The submitted order object from Alpaca.
            
        Raises:
            ValueError: If symbol is not available or if both/neither quantity and price are specified.
        """
        #check function imputs
        if (quantity is None and price is None) or (quantity!=None and price!=None):
            raise ValueError("Must specify either quantity or price.")

        if not self.ticker_service.is_tradable_stock_symbol(symbol):
            self._logger.log_warning(f"Symbol '{symbol}' is not active/tradable on Alpaca. Skipping sell.")
            return None
        
        if quantity is None:
            self._logger.log_info(f"Selling {price} dollars of {symbol}.")
            market_order_data = MarketOrderRequest(
                                symbol=symbol,
                                notional=price,
                                side=side,
                                time_in_force=time_in_force
                            )
        else:
            self._logger.log_info(f"Selling {quantity} shares of {symbol}.")
            market_order_data = MarketOrderRequest(
                                symbol=symbol,
                                qty=quantity,
                                side=side,
                                time_in_force=time_in_force
                            )
        try:
            market_order: Order = self.trading_client.submit_order(market_order_data)
        except APIError as e:
            self._logger.log_warning(f"Alpaca rejected sell for '{symbol}'. Skipping. Error: {e}")
            return None
        except RequestsConnectionError as e:
            self._logger.log_warning(f"Connection error placing sell for '{symbol}'. Skipping. Error: {e}")
            return None
        except RequestsTimeout as e:
            self._logger.log_warning(f"Timeout placing sell for '{symbol}'. Skipping. Error: {e}")
            return None

        return market_order

    def cancel_all_orders(self) -> List:
        """
        Cancel all open orders.
        
        Returns:
            List: List of cancel status objects for each cancelled order.
        """
        cancel_statuses = self.trading_client.cancel_orders()
        return cancel_statuses

class StockTrader(Trader, metaclass=SingletonMeta):
    """
    Specialized trader for US equity (stock) trading.
    
    Extends the base Trader class with stock-specific functionality including
    quote retrieval and historical bar data. Implements the Singleton pattern
    to ensure only one instance exists.
    
    Attributes:
        asset_class (str): Set to 'us_equity' for stock trading.
    """
    
    def __init__(self, *args, **kwargs) -> None:
        """
        Initialize the StockTrader instance.
        
        Args:
            *args: Variable length argument list passed to parent Trader class.
            **kwargs: Arbitrary keyword arguments passed to parent Trader class.
        """
        super().__init__(*args, **kwargs)
        self._logger.log_debug("Instace of Stock_Trader() class created.")
        self.asset_class = 'us_equity'

    def get_quote(self, symbol: str) -> Quote:
        """
        Get the latest quote for a stock symbol.
        
        Args:
            symbol (str): The stock symbol to query.
            
        Returns:
            Quote: The latest quote object containing bid, ask, and other price data.
        """
        client = StockHistoricalDataClient(self.alpaca_client.api_id, self.alpaca_client.secret_key)
        multisymbol_request_params = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        return client.get_stock_latest_quote(multisymbol_request_params)[symbol]

    def get_bars(self, symbol: str, start: datetime, end: datetime, time_resolution: str = 'day') -> pd.DataFrame:
        """
        Retrieve historical bar data for a stock symbol.
        
        Args:
            symbol (str): The stock symbol to query.
            start (datetime): Start date/time for the historical data.
            end (datetime): End date/time for the historical data.
            time_resolution (str, optional): Time resolution for bars ('day', 'hour', 'minute'). Defaults to 'day'.
            
        Returns:
            pd.DataFrame: DataFrame containing historical bar data (open, high, low, close, volume).
        """

        client = StockHistoricalDataClient(self.alpaca_client.api_id, self.alpaca_client.secret_key)
        request_params = StockBarsRequest(
                        symbol_or_symbols=symbol,
                        timeframe=self.timeframe_lookup[time_resolution],
                        start=start,
                        end=end
                 )

        bars = client.get_stock_bars(request_params)
        return bars.df

class CryptoTrader(Trader, metaclass=SingletonMeta):
    """
    Specialized trader for cryptocurrency trading.
    
    Extends the base Trader class with crypto-specific functionality including
    quote retrieval and historical bar data.
    
    Attributes:
        asset_class (str): Set to 'crypto' for cryptocurrency trading.
    """
    
    def __init__(self, *args, **kwargs) -> None:
        """
        Initialize the CryptoTrader instance.
        
        Args:
            *args: Variable length argument list passed to parent Trader class.
            **kwargs: Arbitrary keyword arguments passed to parent Trader class.
        """
        super().__init__(*args, **kwargs)
        self._logger.log_debug("Instace of Crypto_Trader() class created.")
        self.asset_class = 'crypto'

    def get_quote(self, symbol: str):
        """
        Get the latest quote for a cryptocurrency symbol.
        
        Args:
            symbol (str): The cryptocurrency symbol to query.
            
        Returns:
            Quote: The latest quote object containing bid, ask, and other price data.
        """
        client = CryptoHistoricalDataClient(self.alpaca_client.api_id, self.alpaca_client.secret_key)
        multisymbol_request_params = CryptoLatestQuoteRequest(symbol_or_symbols=symbol)
        return client.get_crypto_latest_quote(multisymbol_request_params)[symbol]

    def get_bars(self, symbol: str, start: datetime, end: datetime, time_resolution: str = 'day') -> pd.DataFrame:
        """
        Retrieve historical bar data for a cryptocurrency symbol.
        
        Args:
            symbol (str): The cryptocurrency symbol to query.
            start (datetime): Start date/time for the historical data.
            end (datetime): End date/time for the historical data.
            time_resolution (str, optional): Time resolution for bars ('day', 'hour', 'minute'). Defaults to 'day'.
            
        Returns:
            pd.DataFrame: DataFrame containing historical bar data (open, high, low, close, volume).
        """
        client = CryptoHistoricalDataClient()
        request_params = CryptoBarsRequest(
                        symbol_or_symbols=symbol,
                        timeframe=self.timeframe_lookup[time_resolution],
                        start=start,
                        end=end
                 )
        bars = client.get_crypto_bars(request_params)
        return bars.df


if __name__ == "__main__":
    pass