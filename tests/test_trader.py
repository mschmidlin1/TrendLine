import unittest
import sys
import os
from src.trader import StockTrader
from src.configs import ALPACA_API_ID_PAPER, ALPACA_SECRET_KEY_PAPER
# Add src directory to path
from alpaca.data.models.quotes import Quote
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus
from src.base.alpaca_client import AlpacaClient
from src.converters import orders_to_dataframe, positions_to_dataframe

class TestTrader(unittest.TestCase):
    """Unit tests for SentimentService class."""

    def test_stock_trader_initialize(self):
            """Test that batch analysis handles individual errors gracefully."""
            stock_trader = StockTrader(alpaca_client = AlpacaClient(ALPACA_API_ID_PAPER, ALPACA_SECRET_KEY_PAPER, True))
    def test_stock_trader_get_quote(self):
            """Test that batch analysis handles individual errors gracefully."""
            stock_trader = StockTrader(alpaca_client = AlpacaClient(ALPACA_API_ID_PAPER, ALPACA_SECRET_KEY_PAPER, True))
            result: Quote = stock_trader.get_quote("AAPL")
            print("\nAsk Price (price seller is willing to accept):", result.ask_price)
            print("Bid Price (price buyer is willing to pay):", result.bid_price)
            print("Ask Exchange:", result.ask_exchange)
            print("Bid Exchange:", result.bid_exchange)
            print("Ask Size:", result.ask_size)
            print("Bid Size:", result.bid_size)
            print(result)
    def test_stock_trader_get_all_positions(self):
            """Test that batch analysis handles individual errors gracefully."""
            stock_trader = StockTrader(alpaca_client = AlpacaClient(ALPACA_API_ID_PAPER, ALPACA_SECRET_KEY_PAPER, True))
            positions = stock_trader.get_all_positions()
            positions_df = positions_to_dataframe(positions)
            print(positions_df.shape)
            print(positions_df.columns)
            print(positions_df)
    def test_stock_trader_get_all_orders(self):
            """Test that batch analysis handles individual errors gracefully."""
            stock_trader = StockTrader(alpaca_client = AlpacaClient(ALPACA_API_ID_PAPER, ALPACA_SECRET_KEY_PAPER, True))
            orders = stock_trader.get_orders()
            orders_df = orders_to_dataframe(orders)
            print(orders_df.shape)
            print(orders_df.columns)
    def test_stock_trader_get_open_orders(self):
            """Test that batch analysis handles individual errors gracefully."""
            stock_trader = StockTrader(alpaca_client = AlpacaClient(ALPACA_API_ID_PAPER, ALPACA_SECRET_KEY_PAPER, True))
            orders = stock_trader.get_orders_open()
            orders_df = orders_to_dataframe(orders)
            print(orders_df.shape)
            print(orders_df.columns) 
    def test_buy(self):
            """Test that batch analysis handles individual errors gracefully."""
            stock_trader = StockTrader(alpaca_client = AlpacaClient(ALPACA_API_ID_PAPER, ALPACA_SECRET_KEY_PAPER, True))
        #     order = stock_trader.buy("GLW", price=10.0, time_in_force=TimeInForce.DAY)
        #     print(order.status)
        #     print(order.id)
    
# ACCEPTED =
# <OrderStatus.ACCEPTED: 'accepted'>
# ACCEPTED_FOR_BIDDING =
# <OrderStatus.ACCEPTED_FOR_BIDDING: 'accepted_for_bidding'>
# CALCULATED =
# <OrderStatus.CALCULATED: 'calculated'>
# CANCELED =
# <OrderStatus.CANCELED: 'canceled'>
# DONE_FOR_DAY =
# <OrderStatus.DONE_FOR_DAY: 'done_for_day'>
# EXPIRED =
# <OrderStatus.EXPIRED: 'expired'>
# FILLED =
# <OrderStatus.FILLED: 'filled'>
# HELD =
# <OrderStatus.HELD: 'held'>
# NEW =
# <OrderStatus.NEW: 'new'>
# PARTIALLY_FILLED =
# <OrderStatus.PARTIALLY_FILLED: 'partially_filled'>
# PENDING_CANCEL =
# <OrderStatus.PENDING_CANCEL: 'pending_cancel'>
# PENDING_NEW =
# <OrderStatus.PENDING_NEW: 'pending_new'>
# PENDING_REPLACE =
# <OrderStatus.PENDING_REPLACE: 'pending_replace'>
# PENDING_REVIEW =
# <OrderStatus.PENDING_REVIEW: 'pending_review'>
# REJECTED =
# <OrderStatus.REJECTED: 'rejected'>
# REPLACED =
# <OrderStatus.REPLACED: 'replaced'>
# STOPPED =
# <OrderStatus.STOPPED: 'stopped'>
# SUSPENDED =
# <OrderStatus.SUSPENDED: 'suspended'>
if __name__ == '__main__':
    unittest.main()
