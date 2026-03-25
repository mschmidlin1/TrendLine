import unittest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from src.sell_tracking_service import SellTrackingService
from alpaca.trading.models import Order
from alpaca.trading.enums import OrderStatus, OrderSide
from src.base.alpaca_client import AlpacaClient
from src.configs import ALPACA_API_ID_PAPER, ALPACA_SECRET_KEY_PAPER


class TestSellTrackingService(unittest.TestCase):
    """Unit tests for SellTrackingService class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Clear singleton instance before each test
        if SellTrackingService in SellTrackingService._instances:
            del SellTrackingService._instances[SellTrackingService]
    
    def test_sell_tracking_service_initialize(self):
        """Test that SellTrackingService initializes correctly."""
        service = SellTrackingService()
        
        # Verify service is initialized
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.alpaca_client)
        self.assertIsNotNone(service.trading_client)
        self.assertIsNotNone(service._logger)
        
        # Verify lists are empty
        self.assertEqual(len(service.tracked_sells), 0)
        self.assertEqual(len(service.fulfilled_sells), 0)
        self.assertIsInstance(service.tracked_sells, list)
        self.assertIsInstance(service.fulfilled_sells, list)
    
    def test_singleton_pattern(self):
        """Test that SellTrackingService follows singleton pattern."""
        service1 = SellTrackingService()
        service2 = SellTrackingService()
        
        # Both instances should be the same object
        self.assertIs(service1, service2)
    
    def test_log_sell(self):
        """Test logging a sell order with its corresponding buy order."""
        service = SellTrackingService()
        
        # Create mock orders
        buy_order = Mock(spec=Order)
        buy_order.symbol = "AAPL"
        buy_order.qty = 10
        buy_order.id = "buy-123"
        
        sell_order = Mock(spec=Order)
        sell_order.symbol = "AAPL"
        sell_order.qty = 10
        sell_order.id = "sell-456"
        
        # Log the sell order
        service.log_sell(buy_order, sell_order)
        
        # Verify order was added to tracked_sells
        self.assertEqual(len(service.tracked_sells), 1)
        self.assertEqual(service.tracked_sells[0]['buy_order'], buy_order)
        self.assertEqual(service.tracked_sells[0]['sell_order'], sell_order)
        self.assertIn('logged_at', service.tracked_sells[0])
        self.assertIsInstance(service.tracked_sells[0]['logged_at'], datetime)
    
    def test_log_multiple_sells(self):
        """Test logging multiple sell orders."""
        service = SellTrackingService()
        
        # Create and log multiple orders
        for i in range(3):
            buy_order = Mock(spec=Order)
            buy_order.symbol = f"STOCK{i}"
            buy_order.qty = 10 + i
            buy_order.id = f"buy-{i}"
            
            sell_order = Mock(spec=Order)
            sell_order.symbol = f"STOCK{i}"
            sell_order.qty = 10 + i
            sell_order.id = f"sell-{i}"
            
            service.log_sell(buy_order, sell_order)
        
        # Verify all orders were added
        self.assertEqual(len(service.tracked_sells), 3)
    
    @patch.object(SellTrackingService, '_check_statuses')
    def test_update_fetches_order_status(self, mock_check_statuses):
        """Test that update() fetches fresh order status from Alpaca."""
        service = SellTrackingService()
        
        # Create mock orders
        buy_order = Mock(spec=Order)
        buy_order.symbol = "AAPL"
        
        sell_order = Mock(spec=Order)
        sell_order.symbol = "AAPL"
        sell_order.id = "sell-123"
        sell_order.status = OrderStatus.NEW
        sell_order.qty = 10
        
        # Log the sell order
        service.log_sell(buy_order, sell_order)
        
        # Create updated order with different status
        updated_order = Mock(spec=Order)
        updated_order.symbol = "AAPL"
        updated_order.id = "sell-123"
        updated_order.status = OrderStatus.FILLED
        
        # Mock the trading client to return updated order
        service.trading_client.get_order_by_id = Mock(return_value=updated_order)
        
        # Call update
        service.update()
        
        # Verify get_order_by_id was called
        service.trading_client.get_order_by_id.assert_called_once_with("sell-123")
        
        # Verify the order in tracked_sells was updated
        self.assertEqual(service.tracked_sells[0]['sell_order'], updated_order)
        
        # Verify _check_statuses was called
        mock_check_statuses.assert_called_once()
    
    def test_check_statuses_with_filled_order(self):
        """Test that filled orders are moved to fulfilled_sells."""
        service = SellTrackingService()
        
        # Create mock orders
        buy_order = Mock(spec=Order)
        buy_order.symbol = "AAPL"
        
        sell_order = Mock(spec=Order)
        sell_order.symbol = "AAPL"
        sell_order.id = "sell-123"
        sell_order.status = OrderStatus.FILLED
        sell_order.qty = 10
        
        # Manually add to tracked_sells
        service.tracked_sells.append({
            'buy_order': buy_order,
            'sell_order': sell_order,
            'logged_at': datetime.now()
        })
        
        # Call _check_statuses
        service._check_statuses()
        
        # Verify order was moved to fulfilled_sells
        self.assertEqual(len(service.tracked_sells), 0)
        self.assertEqual(len(service.fulfilled_sells), 1)
        self.assertEqual(service.fulfilled_sells[0]['buy_order'], buy_order)
        self.assertEqual(service.fulfilled_sells[0]['sell_order'], sell_order)
        self.assertIn('completed_at', service.fulfilled_sells[0])
    
    def test_check_statuses_with_canceled_order(self):
        """Test that canceled orders are moved to fulfilled_sells."""
        service = SellTrackingService()
        
        # Create mock orders
        buy_order = Mock(spec=Order)
        buy_order.symbol = "AAPL"
        
        sell_order = Mock(spec=Order)
        sell_order.symbol = "AAPL"
        sell_order.id = "sell-123"
        sell_order.status = OrderStatus.CANCELED
        sell_order.qty = 10
        
        # Manually add to tracked_sells
        service.tracked_sells.append({
            'buy_order': buy_order,
            'sell_order': sell_order,
            'logged_at': datetime.now()
        })
        
        # Call _check_statuses
        service._check_statuses()
        
        # Verify order was moved to fulfilled_sells (even though canceled)
        self.assertEqual(len(service.tracked_sells), 0)
        self.assertEqual(len(service.fulfilled_sells), 1)
        self.assertEqual(service.fulfilled_sells[0]['sell_order'].status, OrderStatus.CANCELED)
    
    def test_check_statuses_with_open_order(self):
        """Test that open orders remain in tracked_sells."""
        service = SellTrackingService()
        
        # Create mock orders
        buy_order = Mock(spec=Order)
        buy_order.symbol = "AAPL"
        
        sell_order = Mock(spec=Order)
        sell_order.symbol = "AAPL"
        sell_order.id = "sell-123"
        sell_order.status = OrderStatus.ACCEPTED
        
        # Manually add to tracked_sells
        service.tracked_sells.append({
            'buy_order': buy_order,
            'sell_order': sell_order,
            'logged_at': datetime.now()
        })
        
        # Call _check_statuses
        service._check_statuses()
        
        # Verify order remains in tracked_sells
        self.assertEqual(len(service.tracked_sells), 1)
        self.assertEqual(len(service.fulfilled_sells), 0)
    
    def test_multiple_orders_tracking(self):
        """Test tracking multiple orders with different statuses."""
        service = SellTrackingService()
        
        # Create orders with different statuses
        orders_data = [
            (OrderStatus.FILLED, "AAPL"),
            (OrderStatus.ACCEPTED, "GOOGL"),
            (OrderStatus.CANCELED, "MSFT"),
            (OrderStatus.NEW, "TSLA"),
        ]
        
        for status, symbol in orders_data:
            buy_order = Mock(spec=Order)
            buy_order.symbol = symbol
            
            sell_order = Mock(spec=Order)
            sell_order.symbol = symbol
            sell_order.id = f"sell-{symbol}"
            sell_order.status = status
            sell_order.qty = 10
            
            service.tracked_sells.append({
                'buy_order': buy_order,
                'sell_order': sell_order,
                'logged_at': datetime.now()
            })
        
        # Call _check_statuses
        service._check_statuses()
        
        # Verify correct distribution
        # FILLED and CANCELED should be in fulfilled_sells (2 orders)
        self.assertEqual(len(service.fulfilled_sells), 2)
        # ACCEPTED and NEW should remain in tracked_sells (2 orders)
        self.assertEqual(len(service.tracked_sells), 2)
        
        # Verify the correct orders are in each list
        tracked_symbols = [order['sell_order'].symbol for order in service.tracked_sells]
        self.assertIn("GOOGL", tracked_symbols)
        self.assertIn("TSLA", tracked_symbols)
        
        fulfilled_symbols = [order['sell_order'].symbol for order in service.fulfilled_sells]
        self.assertIn("AAPL", fulfilled_symbols)
        self.assertIn("MSFT", fulfilled_symbols)


if __name__ == '__main__':
    unittest.main()
