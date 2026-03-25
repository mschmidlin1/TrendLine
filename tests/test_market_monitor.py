import unittest
import sys
import os
from src.market_monitor import MarketMonitorService
from src.configs import ALPACA_API_ID_PAPER, ALPACA_SECRET_KEY_PAPER
# Add src directory to path
from alpaca.data.models.quotes import Quote


class TestMarketMonitor(unittest.TestCase):
    """Unit tests for SentimentService class."""

    def test_stock_trader_initialize(self):
            """Test that batch analysis handles individual errors gracefully."""
            market_monitor = MarketMonitorService()
    

    
if __name__ == '__main__':
    unittest.main()
