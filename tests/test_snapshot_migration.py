import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

from alpaca.trading.enums import OrderStatus
from alpaca.trading.models import Order

from src.snapshot_migration import migrate_legacy_archived_entry_in_place
from src.base.sentiment_response import SentimentResponse


def _legacy_article():
    return {"title": "t", "link": "https://example.com/x", "published": "", "summary": ""}


def _sentiment():
    return SentimentResponse(
        "positive", "NVDA", True, True, "Positive | NVDA",
    )


def _mock_order(symbol="NVDA"):
    order = Mock(spec=Order)
    order.id = uuid4()
    order.symbol = symbol
    order.qty = "1"
    order.status = OrderStatus.NEW
    order.filled_at = None
    order.filled_avg_price = None
    order.notional = None
    return order


class TestSnapshotMigration(unittest.TestCase):
    def test_migrate_no_buy_empty_dicts(self):
        entry = {
            "article_id": "https://example.com/x",
            "source_name": "CNBC",
            "article_entry": _legacy_article(),
            "sentiment_response": _sentiment(),
            "buy_order": None,
            "sell_order": None,
            "buy_order_terminal": True,
            "sell_order_terminal": True,
            "resulted_in_purchase": False,
            "archived_at": datetime.now(timezone.utc),
        }
        migrate_legacy_archived_entry_in_place(entry)
        self.assertEqual(entry["buy_orders"], {})
        self.assertEqual(entry["sell_orders"], {})
        self.assertEqual(entry["buy_order_terminal"], {})
        self.assertEqual(entry["sell_order_terminal"], {})
        self.assertNotIn("buy_order", entry)

    def test_migrate_buy_only(self):
        bo = _mock_order("NVDA")
        entry = {
            "article_id": "https://example.com/x",
            "buy_order": bo,
            "sell_order": None,
            "buy_order_terminal": False,
            "sell_order_terminal": True,
        }
        migrate_legacy_archived_entry_in_place(entry)
        self.assertEqual(entry["buy_orders"]["NVDA"], bo)
        self.assertIsNone(entry["sell_orders"]["NVDA"])
        self.assertFalse(entry["buy_order_terminal"]["NVDA"])
        self.assertTrue(entry["sell_order_terminal"]["NVDA"])

    def test_migrate_buy_and_sell(self):
        bo = _mock_order("AAPL")
        so = _mock_order("AAPL")
        entry = {
            "buy_order": bo,
            "sell_order": so,
            "buy_order_terminal": True,
            "sell_order_terminal": False,
        }
        migrate_legacy_archived_entry_in_place(entry)
        self.assertEqual(entry["buy_orders"]["AAPL"], bo)
        self.assertEqual(entry["sell_orders"]["AAPL"], so)
        self.assertTrue(entry["buy_order_terminal"]["AAPL"])
        self.assertFalse(entry["sell_order_terminal"]["AAPL"])

    def test_migrate_idempotent_when_already_dict_shape(self):
        bo = _mock_order()
        entry = {"buy_orders": {"NVDA": bo}, "sell_orders": {"NVDA": None}}
        migrate_legacy_archived_entry_in_place(entry)
        self.assertEqual(entry["buy_orders"]["NVDA"], bo)


if __name__ == "__main__":
    unittest.main()
