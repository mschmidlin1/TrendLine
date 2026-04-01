from alpaca.data import Trade
from src.base.singleton import SingletonMeta
from alpaca.trading.requests import GetPortfolioHistoryRequest
from src.base.alpaca_client import AlpacaClient
from alpaca.trading.client import TradingClient
from datetime import datetime
from alpaca.trading.models import Order, Position, TradeAccount
from typing import List

class AccountService(metaclass=SingletonMeta):
    def __init__(self):
        self.alpaca_client = AlpacaClient()
        self.trading_client: TradingClient = self.alpaca_client.trading_client
        self.update_account()

    def get_equity_history(self, **kwargs):
        """
        Fetches the historical equity/portfolio value for the account using 
        dynamic keyword arguments.

        Args:
            **kwargs: Arbitrary keyword arguments passed to GetPortfolioHistoryRequest.
                Common keys include:
                - period (str): Duration (e.g., '1D', '1M', '1Y', 'all').
                - timeframe (str): Resolution (e.g., '1Min', '5Min', '1H', '1D').
                - start (datetime): Specific start date.
                - end (datetime): Specific end date.
                - extended_hours (bool): Include pre/post market data.

        Returns:
            PortfolioHistory: Object containing equity, timestamp, and P/L data.
        """
        # Unpack kwargs directly into the request object
        history_params = GetPortfolioHistoryRequest(**kwargs)
        
        # Execute the query
        return self.trading_client.get_portfolio_history(history_params)

    def get_all_positions(self) -> List[Position]:
        """Open stock and crypto positions for the account."""
        return self.trading_client.get_all_positions()

    def get_history_1d(self):
        """Last 24 hours at 1-minute resolution."""
        return self.get_equity_history(period="1D", timeframe="1Min", intraday_reporting="continuous")

    def get_history_1w(self):
        """Last 7 days at 1-hour resolution."""
        return self.get_equity_history(period="1W", timeframe="1H", intraday_reporting="continuous")

    def get_history_1m(self):
        """Last 30 days at 1-hour resolution."""
        return self.get_equity_history(period="28D", timeframe="1H", intraday_reporting="continuous")

    def get_history_3m(self):
        """Last 90 days at 1-day resolution."""
        return self.get_equity_history(period="3M", timeframe="1D")

    def get_history_ytd(self):
        """From Jan 1st of the current year to now at 1-day resolution."""
        start_of_year = datetime(datetime.now().year, 1, 1)
        # Note: Alpaca calculates YTD best by passing the 'start' date
        return self.get_equity_history(start=start_of_year, timeframe="1D")

    def get_history_1y(self):
        """Last 365 days at 1-day resolution."""
        return self.get_equity_history(period="12M", timeframe="1D")

    def get_history_all(self):
        """Entire account history at 1-day resolution."""
        return self.get_equity_history(period="all", timeframe="1D")

    def update_account(self):
        self.account: TradeAccount = self.trading_client.get_account()

    def get_available_cash(self) -> float:
        """
        Get the cash available from the alpaca account.
        """
        self.update_account()
        return float(self.account.cash)

    def get_buying_power(self) -> float:
        """
        Retrieve and the buying power from alpaca account.
        """
        self.update_account()
        return float(self.account.buying_power)
    

