import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.trade_lifecycle_manager import TradeLifecycleManager
from src.base.sentiment_response import SentimentResponse
from alpaca.trading.models import Order
from alpaca.trading.enums import OrderStatus
from src.configs import MARKET_HOLD_TIME


def _make_article_entry(link="https://example.com/article/123", title="Test Article",
                        published="Mon, 24 Mar 2026 10:30:00 GMT",
                        summary="Test summary text"):
    """Helper to create a mock FeedParserDict-like article entry."""
    return {
        'title': title,
        'link': link,
        'published': published,
        'summary': summary,
        'id': link,
    }


def _make_sentiment_response(sentiment="positive", ticker="NVDA",
                              format_match=True, ticker_found=True,
                              raw_response="Positive | NVDA"):
    """Helper to create a SentimentResponse."""
    return SentimentResponse(
        sentiment=sentiment,
        ticker=ticker,
        format_match=format_match,
        ticker_found=ticker_found,
        raw_response=raw_response,
    )


def _make_mock_order(symbol="NVDA", qty="10", status=OrderStatus.NEW,
                     order_id=None, filled_at=None, filled_avg_price=None,
                     notional=None):
    """Helper to create a mock Order object."""
    order = Mock(spec=Order)
    order.id = order_id or uuid4()
    order.symbol = symbol
    order.qty = qty
    order.status = status
    order.filled_at = filled_at
    order.filled_avg_price = filled_avg_price
    order.notional = notional
    return order


class TestTradeLifecycleManager(unittest.TestCase):
    """Unit tests for TradeLifecycleManager class."""

    def setUp(self):
        """Clear singleton instance before each test."""
        if TradeLifecycleManager in TradeLifecycleManager._instances:
            del TradeLifecycleManager._instances[TradeLifecycleManager]

    # ---------------------------------------------------------------
    # 1. test_trade_lifecycle_manager_initialize
    # ---------------------------------------------------------------
    def test_trade_lifecycle_manager_initialize(self):
        """Verify service initializes correctly with all attributes."""
        manager = TradeLifecycleManager()

        self.assertIsNotNone(manager)
        self.assertIsNotNone(manager._logger)
        self.assertIsNotNone(manager.alpaca_client)
        self.assertIsNotNone(manager.trading_client)
        self.assertIsInstance(manager.archived_entries, list)
        self.assertEqual(len(manager.archived_entries), 0)
        self.assertIsInstance(manager._article_id_index, dict)
        self.assertEqual(len(manager._article_id_index), 0)
        self.assertIsInstance(manager._buy_order_id_index, dict)
        self.assertEqual(len(manager._buy_order_id_index), 0)
        self.assertIsInstance(manager.ready_to_sell, list)
        self.assertEqual(len(manager.ready_to_sell), 0)

    # ---------------------------------------------------------------
    # 2. test_singleton_pattern
    # ---------------------------------------------------------------
    def test_singleton_pattern(self):
        """Verify singleton behavior — two instances are the same object."""
        manager1 = TradeLifecycleManager()
        manager2 = TradeLifecycleManager()
        self.assertIs(manager1, manager2)

    # ---------------------------------------------------------------
    # 3. test_archive_news_entry_success
    # ---------------------------------------------------------------
    def test_archive_news_entry_success(self):
        """Archive a news entry successfully and verify all fields."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order()

        result = manager.archive_news_entry("CNBC", article, sentiment, buy_order)

        self.assertTrue(result)
        self.assertEqual(len(manager.archived_entries), 1)

        entry = manager.archived_entries[0]
        self.assertEqual(entry['article_id'], "https://example.com/article/123")
        self.assertEqual(entry['source_name'], "CNBC")
        self.assertEqual(entry['article_entry'], article)
        self.assertEqual(entry['sentiment_response'], sentiment)
        self.assertEqual(entry['buy_order'], buy_order)
        self.assertIsNone(entry['sell_order'])
        self.assertIsInstance(entry['archived_at'], datetime)
        self.assertTrue(entry['resulted_in_purchase'])
        self.assertFalse(entry['buy_order_terminal'])
        self.assertTrue(entry['sell_order_terminal'])

    # ---------------------------------------------------------------
    # 4. test_archive_news_entry_with_buy_order
    # ---------------------------------------------------------------
    def test_archive_news_entry_with_buy_order(self):
        """Archive entry with buy order — verify tracking flags and index."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order()

        result = manager.archive_news_entry("CNBC", article, sentiment, buy_order)

        self.assertTrue(result)
        entry = manager.archived_entries[0]
        self.assertTrue(entry['resulted_in_purchase'])
        self.assertEqual(entry['buy_order'], buy_order)
        self.assertFalse(entry['buy_order_terminal'])
        self.assertTrue(entry['sell_order_terminal'])
        # Verify buy order ID index
        self.assertIn(str(buy_order.id), manager._buy_order_id_index)
        self.assertEqual(
            manager._buy_order_id_index[str(buy_order.id)],
            "https://example.com/article/123"
        )

    # ---------------------------------------------------------------
    # 5. test_archive_news_entry_without_buy_order
    # ---------------------------------------------------------------
    def test_archive_news_entry_without_buy_order(self):
        """Archive entry without buy order — verify flags and no index update."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()

        result = manager.archive_news_entry("CNBC", article, sentiment, buy_order=None)

        self.assertTrue(result)
        entry = manager.archived_entries[0]
        self.assertFalse(entry['resulted_in_purchase'])
        self.assertIsNone(entry['buy_order'])
        self.assertTrue(entry['buy_order_terminal'])
        self.assertTrue(entry['sell_order_terminal'])
        self.assertEqual(len(manager._buy_order_id_index), 0)

    # ---------------------------------------------------------------
    # 6. test_archive_news_entry_duplicate
    # ---------------------------------------------------------------
    def test_archive_news_entry_duplicate(self):
        """Attempt to archive same article twice — second should fail."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()

        result1 = manager.archive_news_entry("CNBC", article, sentiment)
        result2 = manager.archive_news_entry("CNBC", article, sentiment)

        self.assertTrue(result1)
        self.assertFalse(result2)
        self.assertEqual(len(manager.archived_entries), 1)

    # ---------------------------------------------------------------
    # 7. test_archive_news_entry_missing_link
    # ---------------------------------------------------------------
    def test_archive_news_entry_missing_link(self):
        """Attempt to archive entry without 'link' field — should fail."""
        manager = TradeLifecycleManager()
        article = {'title': 'No Link Article', 'summary': 'Test'}
        sentiment = _make_sentiment_response()

        result = manager.archive_news_entry("CNBC", article, sentiment)

        self.assertFalse(result)
        self.assertEqual(len(manager.archived_entries), 0)

    # ---------------------------------------------------------------
    # 8. test_log_sell_order_success
    # ---------------------------------------------------------------
    def test_log_sell_order_success(self):
        """Log a sell order against an archived buy order."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order()
        sell_order = _make_mock_order(status=OrderStatus.NEW)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)
        result = manager.log_sell_order(buy_order, sell_order)

        self.assertTrue(result)
        entry = manager.archived_entries[0]
        self.assertEqual(entry['sell_order'], sell_order)
        self.assertFalse(entry['sell_order_terminal'])

    # ---------------------------------------------------------------
    # 9. test_log_sell_order_buy_order_not_found
    # ---------------------------------------------------------------
    def test_log_sell_order_buy_order_not_found(self):
        """Log sell order with unknown buy order — should fail."""
        manager = TradeLifecycleManager()
        buy_order = _make_mock_order()
        sell_order = _make_mock_order()

        result = manager.log_sell_order(buy_order, sell_order)

        self.assertFalse(result)

    # ---------------------------------------------------------------
    # 10. test_log_sell_order_overwrites_existing
    # ---------------------------------------------------------------
    def test_log_sell_order_overwrites_existing(self):
        """Log a second sell order — should overwrite the first."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order()
        sell_order_1 = _make_mock_order(status=OrderStatus.NEW)
        sell_order_2 = _make_mock_order(status=OrderStatus.NEW)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)
        manager.log_sell_order(buy_order, sell_order_1)
        result = manager.log_sell_order(buy_order, sell_order_2)

        self.assertTrue(result)
        entry = manager.archived_entries[0]
        self.assertEqual(entry['sell_order'], sell_order_2)

    # ---------------------------------------------------------------
    # 11. test_update_refreshes_non_terminal_buy_order
    # ---------------------------------------------------------------
    def test_update_refreshes_non_terminal_buy_order(self):
        """Buy order filled with hold period elapsed — should be in ready_to_sell."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(status=OrderStatus.NEW)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)

        # Create updated order that is FILLED with hold period elapsed
        filled_time = datetime.now() - MARKET_HOLD_TIME - timedelta(minutes=5)
        updated_order = _make_mock_order(
            order_id=buy_order.id,
            status=OrderStatus.FILLED,
            filled_at=filled_time,
            filled_avg_price="125.50"
        )
        manager.trading_client.get_order_by_id = Mock(return_value=updated_order)

        manager.update()

        entry = manager.archived_entries[0]
        self.assertEqual(entry['buy_order'], updated_order)
        self.assertTrue(entry['buy_order_terminal'])
        self.assertEqual(len(manager.ready_to_sell), 1)
        self.assertEqual(manager.ready_to_sell[0], updated_order)

    # ---------------------------------------------------------------
    # 12. test_update_buy_order_filled_but_hold_not_elapsed
    # ---------------------------------------------------------------
    def test_update_buy_order_filled_but_hold_not_elapsed(self):
        """Buy order filled but hold period NOT elapsed — should NOT be ready to sell."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(status=OrderStatus.NEW)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)

        # Filled very recently — hold period not elapsed
        filled_time = datetime.now() - timedelta(minutes=1)
        updated_order = _make_mock_order(
            order_id=buy_order.id,
            status=OrderStatus.FILLED,
            filled_at=filled_time,
            filled_avg_price="125.50"
        )
        manager.trading_client.get_order_by_id = Mock(return_value=updated_order)

        manager.update()

        entry = manager.archived_entries[0]
        self.assertEqual(entry['buy_order'], updated_order)
        self.assertFalse(entry['buy_order_terminal'])
        self.assertEqual(len(manager.ready_to_sell), 0)

    # ---------------------------------------------------------------
    # 12b. test_update_buy_order_still_open
    # ---------------------------------------------------------------
    def test_update_buy_order_still_open(self):
        """Buy order still open (ACCEPTED) — should remain non-terminal."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(status=OrderStatus.NEW)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)

        updated_order = _make_mock_order(
            order_id=buy_order.id,
            status=OrderStatus.ACCEPTED
        )
        manager.trading_client.get_order_by_id = Mock(return_value=updated_order)

        manager.update()

        entry = manager.archived_entries[0]
        self.assertEqual(entry['buy_order'], updated_order)
        self.assertFalse(entry['buy_order_terminal'])
        self.assertEqual(len(manager.ready_to_sell), 0)

    # ---------------------------------------------------------------
    # 13. test_update_buy_order_canceled
    # ---------------------------------------------------------------
    def test_update_buy_order_canceled(self):
        """Buy order canceled — should be terminal, NOT in ready_to_sell."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(status=OrderStatus.NEW)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)

        updated_order = _make_mock_order(
            order_id=buy_order.id,
            status=OrderStatus.CANCELED
        )
        manager.trading_client.get_order_by_id = Mock(return_value=updated_order)

        manager.update()

        entry = manager.archived_entries[0]
        self.assertTrue(entry['buy_order_terminal'])
        self.assertEqual(len(manager.ready_to_sell), 0)

    # ---------------------------------------------------------------
    # 14. test_update_buy_order_expired
    # ---------------------------------------------------------------
    def test_update_buy_order_expired(self):
        """Buy order expired — should be terminal, NOT in ready_to_sell."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(status=OrderStatus.NEW)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)

        updated_order = _make_mock_order(
            order_id=buy_order.id,
            status=OrderStatus.EXPIRED
        )
        manager.trading_client.get_order_by_id = Mock(return_value=updated_order)

        manager.update()

        entry = manager.archived_entries[0]
        self.assertTrue(entry['buy_order_terminal'])
        self.assertEqual(len(manager.ready_to_sell), 0)

    # ---------------------------------------------------------------
    # 15. test_update_buy_order_rejected
    # ---------------------------------------------------------------
    def test_update_buy_order_rejected(self):
        """Buy order rejected — should be terminal, NOT in ready_to_sell."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(status=OrderStatus.NEW)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)

        updated_order = _make_mock_order(
            order_id=buy_order.id,
            status=OrderStatus.REJECTED
        )
        manager.trading_client.get_order_by_id = Mock(return_value=updated_order)

        manager.update()

        entry = manager.archived_entries[0]
        self.assertTrue(entry['buy_order_terminal'])
        self.assertEqual(len(manager.ready_to_sell), 0)

    # ---------------------------------------------------------------
    # 16. test_update_refreshes_non_terminal_sell_order
    # ---------------------------------------------------------------
    def test_update_refreshes_non_terminal_sell_order(self):
        """Sell order updated to FILLED — should become terminal."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(status=OrderStatus.FILLED)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)
        # Mark buy order as terminal so update doesn't try to refresh it
        manager.archived_entries[0]['buy_order_terminal'] = True

        sell_order = _make_mock_order(status=OrderStatus.NEW, symbol="NVDA")
        manager.log_sell_order(buy_order, sell_order)

        # Mock trading client to return filled sell order
        updated_sell = _make_mock_order(
            order_id=sell_order.id,
            status=OrderStatus.FILLED,
            filled_avg_price="130.75",
            symbol="NVDA"
        )
        manager.trading_client.get_order_by_id = Mock(return_value=updated_sell)

        manager.update()

        entry = manager.archived_entries[0]
        self.assertEqual(entry['sell_order'], updated_sell)
        self.assertTrue(entry['sell_order_terminal'])

    # ---------------------------------------------------------------
    # 17. test_update_skips_terminal_orders
    # ---------------------------------------------------------------
    def test_update_skips_terminal_orders(self):
        """Both orders terminal — no API calls should be made."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()

        # Archive without buy order — both terminal flags are True
        manager.archive_news_entry("CNBC", article, sentiment, buy_order=None)

        manager.trading_client.get_order_by_id = Mock()

        manager.update()

        manager.trading_client.get_order_by_id.assert_not_called()

    # ---------------------------------------------------------------
    # 18. test_update_handles_mixed_terminal_states
    # ---------------------------------------------------------------
    def test_update_handles_mixed_terminal_states(self):
        """Multiple entries with different terminal states — only non-terminal trigger API calls."""
        manager = TradeLifecycleManager()

        # Entry 1: no buy order (both terminal)
        article1 = _make_article_entry(link="https://example.com/1")
        manager.archive_news_entry("CNBC", article1, _make_sentiment_response())

        # Entry 2: has buy order (buy non-terminal)
        article2 = _make_article_entry(link="https://example.com/2")
        buy_order2 = _make_mock_order(status=OrderStatus.NEW)
        manager.archive_news_entry("MarketWatch", article2, _make_sentiment_response(), buy_order2)

        # Mock: return the same order still in NEW status
        updated_order2 = _make_mock_order(order_id=buy_order2.id, status=OrderStatus.ACCEPTED)
        manager.trading_client.get_order_by_id = Mock(return_value=updated_order2)

        manager.update()

        # Should only be called once (for entry 2's buy order)
        manager.trading_client.get_order_by_id.assert_called_once_with(buy_order2.id)

    # ---------------------------------------------------------------
    # 19. test_check_ready_to_sell
    # ---------------------------------------------------------------
    def test_check_ready_to_sell(self):
        """check_ready_to_sell returns the list without clearing it."""
        manager = TradeLifecycleManager()
        order1 = _make_mock_order()
        order2 = _make_mock_order()
        manager.ready_to_sell = [order1, order2]

        result = manager.check_ready_to_sell()

        self.assertEqual(len(result), 2)
        self.assertIn(order1, result)
        self.assertIn(order2, result)
        # List should NOT be cleared
        self.assertEqual(len(manager.ready_to_sell), 2)

    # ---------------------------------------------------------------
    # 20. test_clear_ready_to_sell
    # ---------------------------------------------------------------
    def test_clear_ready_to_sell(self):
        """clear_ready_to_sell returns the list and clears it."""
        manager = TradeLifecycleManager()
        order1 = _make_mock_order()
        order2 = _make_mock_order()
        manager.ready_to_sell = [order1, order2]

        result = manager.clear_ready_to_sell()

        self.assertEqual(len(result), 2)
        self.assertIn(order1, result)
        self.assertIn(order2, result)
        # List should be cleared
        self.assertEqual(len(manager.ready_to_sell), 0)

    # ---------------------------------------------------------------
    # 21. test_clear_ready_to_sell_empty
    # ---------------------------------------------------------------
    def test_clear_ready_to_sell_empty(self):
        """clear_ready_to_sell on empty list returns empty list."""
        manager = TradeLifecycleManager()

        result = manager.clear_ready_to_sell()

        self.assertEqual(result, [])
        self.assertEqual(manager.ready_to_sell, [])

    # ---------------------------------------------------------------
    # 22. test_full_lifecycle_buy_hold_sell
    # ---------------------------------------------------------------
    def test_full_lifecycle_buy_hold_sell(self):
        """Full lifecycle: archive → fill buy → hold → ready to sell → sell → fill sell."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(status=OrderStatus.NEW, symbol="NVDA")

        # Step 1: Archive with buy order
        manager.archive_news_entry("CNBC", article, sentiment, buy_order)
        self.assertFalse(manager.archived_entries[0]['buy_order_terminal'])

        # Step 2: Update — buy order filled, hold period elapsed
        filled_time = datetime.now() - MARKET_HOLD_TIME - timedelta(minutes=10)
        filled_buy = _make_mock_order(
            order_id=buy_order.id, status=OrderStatus.FILLED,
            filled_at=filled_time, filled_avg_price="125.50", symbol="NVDA"
        )
        manager.trading_client.get_order_by_id = Mock(return_value=filled_buy)
        manager.update()

        self.assertTrue(manager.archived_entries[0]['buy_order_terminal'])
        self.assertEqual(len(manager.ready_to_sell), 1)

        # Step 3: Clear ready to sell
        ready = manager.clear_ready_to_sell()
        self.assertEqual(len(ready), 1)
        self.assertEqual(len(manager.ready_to_sell), 0)

        # Step 4: Log sell order
        sell_order = _make_mock_order(status=OrderStatus.NEW, symbol="NVDA")
        result = manager.log_sell_order(buy_order, sell_order)
        self.assertTrue(result)
        self.assertFalse(manager.archived_entries[0]['sell_order_terminal'])

        # Step 5: Update — sell order filled
        filled_sell = _make_mock_order(
            order_id=sell_order.id, status=OrderStatus.FILLED,
            filled_avg_price="130.75", symbol="NVDA"
        )
        manager.trading_client.get_order_by_id = Mock(return_value=filled_sell)
        manager.update()

        entry = manager.archived_entries[0]
        self.assertTrue(entry['sell_order_terminal'])
        self.assertTrue(entry['buy_order_terminal'])
        self.assertEqual(entry['sell_order'], filled_sell)
        self.assertEqual(entry['buy_order'], filled_buy)

    # ---------------------------------------------------------------
    # 23. test_get_entry_by_article_id_found
    # ---------------------------------------------------------------
    def test_get_entry_by_article_id_found(self):
        """Retrieve an archived entry by article ID."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        manager.archive_news_entry("CNBC", article, sentiment)

        entry = manager.get_entry_by_article_id("https://example.com/article/123")

        self.assertIsNotNone(entry)
        self.assertEqual(entry['article_id'], "https://example.com/article/123")
        self.assertEqual(entry['article_entry'], article)

    # ---------------------------------------------------------------
    # 24. test_get_entry_by_article_id_not_found
    # ---------------------------------------------------------------
    def test_get_entry_by_article_id_not_found(self):
        """Attempt to retrieve non-existent article — returns None."""
        manager = TradeLifecycleManager()

        entry = manager.get_entry_by_article_id("https://nonexistent.com/article")

        self.assertIsNone(entry)

    # ---------------------------------------------------------------
    # 25. test_get_all_entries
    # ---------------------------------------------------------------
    def test_get_all_entries(self):
        """Archive multiple entries and retrieve all."""
        manager = TradeLifecycleManager()
        for i in range(3):
            article = _make_article_entry(link=f"https://example.com/article/{i}")
            manager.archive_news_entry(f"Source{i}", article, _make_sentiment_response())

        entries = manager.get_all_entries()

        self.assertEqual(len(entries), 3)

    # ---------------------------------------------------------------
    # 26. test_to_dataframe_empty
    # ---------------------------------------------------------------
    def test_to_dataframe_empty(self):
        """to_dataframe with no entries returns empty DataFrame with correct columns."""
        manager = TradeLifecycleManager()

        df = manager.to_dataframe()

        self.assertEqual(len(df), 0)
        expected_cols = [
            'article_id', 'source_name', 'title', 'link', 'published_date', 'summary',
            'sentiment', 'ticker', 'format_match', 'ticker_found', 'raw_sentiment_response',
            'resulted_in_purchase', 'archived_at',
            'buy_order_id', 'buy_order_symbol', 'buy_order_qty', 'buy_order_status',
            'buy_order_filled_at', 'buy_order_filled_avg_price', 'buy_order_terminal',
            'sell_order_id', 'sell_order_symbol', 'sell_order_qty', 'sell_order_status',
            'sell_order_filled_at', 'sell_order_filled_avg_price', 'sell_order_terminal',
        ]
        self.assertListEqual(list(df.columns), expected_cols)

    # ---------------------------------------------------------------
    # 27. test_to_dataframe_single_entry_no_order
    # ---------------------------------------------------------------
    def test_to_dataframe_single_entry_no_order(self):
        """Single entry without buy order — buy/sell columns should be None."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        manager.archive_news_entry("CNBC", article, sentiment)

        df = manager.to_dataframe()

        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row['article_id'], "https://example.com/article/123")
        self.assertEqual(row['source_name'], "CNBC")
        self.assertEqual(row['sentiment'], "positive")
        self.assertEqual(row['ticker'], "NVDA")
        self.assertFalse(row['resulted_in_purchase'])
        self.assertIsNone(row['buy_order_id'])
        self.assertIsNone(row['sell_order_id'])

    # ---------------------------------------------------------------
    # 28. test_to_dataframe_single_entry_with_buy_order
    # ---------------------------------------------------------------
    def test_to_dataframe_single_entry_with_buy_order(self):
        """Single entry with buy order — buy columns populated, sell columns None."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(symbol="NVDA", qty="10", status=OrderStatus.NEW)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)

        df = manager.to_dataframe()

        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertTrue(row['resulted_in_purchase'])
        self.assertEqual(row['buy_order_id'], str(buy_order.id))
        self.assertEqual(row['buy_order_symbol'], "NVDA")
        self.assertEqual(row['buy_order_qty'], 10.0)
        self.assertIsNone(row['sell_order_id'])

    # ---------------------------------------------------------------
    # 29. test_to_dataframe_entry_with_buy_and_sell_orders
    # ---------------------------------------------------------------
    def test_to_dataframe_entry_with_buy_and_sell_orders(self):
        """Entry with both buy and sell orders — all columns populated."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(
            symbol="NVDA", qty="10", status=OrderStatus.FILLED,
            filled_avg_price="125.50"
        )
        sell_order = _make_mock_order(
            symbol="NVDA", qty="10", status=OrderStatus.FILLED,
            filled_avg_price="130.75"
        )

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)
        manager.log_sell_order(buy_order, sell_order)

        df = manager.to_dataframe()

        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row['buy_order_id'], str(buy_order.id))
        self.assertEqual(row['buy_order_filled_avg_price'], 125.50)
        self.assertEqual(row['sell_order_id'], str(sell_order.id))
        self.assertEqual(row['sell_order_filled_avg_price'], 130.75)

    # ---------------------------------------------------------------
    # 30. test_to_dataframe_multiple_entries
    # ---------------------------------------------------------------
    def test_to_dataframe_multiple_entries(self):
        """Multiple entries (mix with/without orders) — correct row count and data."""
        manager = TradeLifecycleManager()

        # Entry 1: with buy order
        article1 = _make_article_entry(link="https://example.com/1", title="Article 1")
        buy_order1 = _make_mock_order(symbol="AAPL", qty="5", status=OrderStatus.NEW)
        manager.archive_news_entry("CNBC", article1, _make_sentiment_response(), buy_order1)

        # Entry 2: without buy order
        article2 = _make_article_entry(link="https://example.com/2", title="Article 2")
        manager.archive_news_entry("MarketWatch", article2, _make_sentiment_response(sentiment="neutral"))

        # Entry 3: with buy order
        article3 = _make_article_entry(link="https://example.com/3", title="Article 3")
        buy_order3 = _make_mock_order(symbol="GOOGL", qty="3", status=OrderStatus.FILLED)
        manager.archive_news_entry("WSJ", article3, _make_sentiment_response(), buy_order3)

        df = manager.to_dataframe()

        self.assertEqual(len(df), 3)
        self.assertEqual(df.iloc[0]['source_name'], "CNBC")
        self.assertEqual(df.iloc[1]['source_name'], "MarketWatch")
        self.assertEqual(df.iloc[2]['source_name'], "WSJ")
        self.assertTrue(df.iloc[0]['resulted_in_purchase'])
        self.assertFalse(df.iloc[1]['resulted_in_purchase'])
        self.assertTrue(df.iloc[2]['resulted_in_purchase'])

    # ---------------------------------------------------------------
    # 31. test_to_dataframe_with_updated_order_status
    # ---------------------------------------------------------------
    def test_to_dataframe_with_updated_order_status(self):
        """Archive with NEW buy order, update to FILLED, verify DataFrame shows FILLED."""
        manager = TradeLifecycleManager()
        article = _make_article_entry()
        sentiment = _make_sentiment_response()
        buy_order = _make_mock_order(status=OrderStatus.NEW)

        manager.archive_news_entry("CNBC", article, sentiment, buy_order)

        # Update to FILLED with hold period elapsed
        filled_time = datetime.now() - MARKET_HOLD_TIME - timedelta(minutes=5)
        updated_order = _make_mock_order(
            order_id=buy_order.id,
            status=OrderStatus.FILLED,
            filled_at=filled_time,
            filled_avg_price="125.50"
        )
        manager.trading_client.get_order_by_id = Mock(return_value=updated_order)
        manager.update()

        df = manager.to_dataframe()

        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row['buy_order_status'], str(OrderStatus.FILLED))
        self.assertEqual(row['buy_order_filled_avg_price'], 125.50)

    # ---------------------------------------------------------------
    # 32. test_to_dataframe_preserves_feedparser_data
    # ---------------------------------------------------------------
    def test_to_dataframe_preserves_feedparser_data(self):
        """Verify all FeedParserDict fields are extracted to DataFrame columns."""
        manager = TradeLifecycleManager()
        article = _make_article_entry(
            link="https://example.com/full-article",
            title="Full Article Title",
            published="Tue, 25 Mar 2026 14:00:00 GMT",
            summary="This is the full article summary."
        )
        sentiment = _make_sentiment_response()
        manager.archive_news_entry("FinancialTimes", article, sentiment)

        df = manager.to_dataframe()

        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row['title'], "Full Article Title")
        self.assertEqual(row['link'], "https://example.com/full-article")
        self.assertEqual(row['published_date'], "Tue, 25 Mar 2026 14:00:00 GMT")
        self.assertEqual(row['summary'], "This is the full article summary.")

    def test_restore_migrates_naive_archived_at(self):
        """Naive archived_at from old snapshots becomes UTC-aware on restore."""
        manager = TradeLifecycleManager()
        naive_at = datetime(2024, 6, 1, 12, 0, 0)
        snapshot = {
            "archived_entries": [
                {
                    "article_id": "https://example.com/migrated",
                    "archived_at": naive_at,
                }
            ],
            "_article_id_index": {},
            "_buy_order_id_index": {},
            "ready_to_sell": [],
        }
        manager.restore_from_persistent_snapshot(snapshot)
        at = manager.archived_entries[0]["archived_at"]
        self.assertIsNotNone(at.tzinfo)
        self.assertEqual(at.tzinfo, timezone.utc)
        self.assertEqual(at.timestamp(), naive_at.timestamp())


if __name__ == '__main__':
    unittest.main()