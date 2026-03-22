import unittest
import sys
import os
from src.ticker_service import TickerService
from src.configs import ALPACA_API_ID_PAPER, ALPACA_SECRET_KEY_PAPER
# Add src directory to path
from alpaca.data.models.quotes import Quote


class TestTickerService(unittest.TestCase):
    """Unit tests for SentimentService class."""

    def test_get_available_symbols_stocks(self):
            ticker_service = TickerService()
            symbols = ticker_service.get_available_symbols(asset_class="us_equity")
            print(len(symbols))
            print(symbols[:5])
            self.assertTrue("TSLA" in symbols)
            self.assertTrue("AAPL" in symbols)
            self.assertTrue("GLW" in symbols)
    
    def test_get_available_symbols_crypto(self):
            ticker_service = TickerService()
            symbols = ticker_service.get_available_symbols(asset_class="crypto")
            print(len(symbols))
            print(symbols[:5])

    def test_is_stock_symbol_false(self):
            ticker_service = TickerService()
            is_stock = ticker_service.is_stock_symbol("ZZZZZZ")
            self.assertFalse(is_stock)

    def test_is_stock_symbol_true(self):
            ticker_service = TickerService()
            is_stock = ticker_service.is_stock_symbol("GLW")
            self.assertTrue(is_stock)

if __name__ == '__main__':
    unittest.main()
