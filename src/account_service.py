from src.base.singleton import SingletonMeta
from alpaca.trading.requests import GetPortfolioHistoryRequest
from src.base.alpaca_client import AlpacaClient
from alpaca.trading.client import TradingClient
from datetime import datetime

class HistoricalDataService(metaclass=SingletonMeta):
    def __init__(self):
        self.alpaca_client = AlpacaClient()
        self.trading_client: TradingClient = self.alpaca_client.trading_client

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
    def get_history_1d(self):
        """Last 24 hours at 1-minute resolution."""
        return self.get_equity_history(period="1D", timeframe="1Min")

    def get_history_1w(self):
        """Last 7 days at 1-hour resolution."""
        return self.get_equity_history(period="1W", timeframe="1H")

    def get_history_1m(self):
        """Last 30 days at 1-hour resolution."""
        return self.get_equity_history(period="1M", timeframe="1H")

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
        return self.get_equity_history(period="1Y", timeframe="1D")

    def get_history_all(self):
        """Entire account history at 1-day resolution."""
        return self.get_equity_history(period="all", timeframe="1D")
