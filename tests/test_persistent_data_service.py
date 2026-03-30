import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import feedparser

from src.news_scraper import NewsScrapingService
from src.persistent_data_service import PersistentDataService
from src.trade_lifecycle_manager import TradeLifecycleManager


def _clear_singletons():
    for cls in (PersistentDataService, TradeLifecycleManager, NewsScrapingService):
        if cls in cls._instances:
            del cls._instances[cls]


class TestPersistentDataService(unittest.TestCase):
    def setUp(self):
        _clear_singletons()
        PersistentDataService._SHUTDOWN_SAVE_DONE = False
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        _clear_singletons()
        PersistentDataService._SHUTDOWN_SAVE_DONE = False

    def test_round_trip_trade_and_news_snapshots(self):
        tmp = Path(self._tmp)
        tm = TradeLifecycleManager()
        tm.archived_entries = []
        tm._article_id_index = {}
        tm._buy_order_id_index = {}
        tm.ready_to_sell = []

        NewsScrapingService(
            rss_feeds={"TestSource": "http://example.com/feed"},
            skip_initial_scrape=True,
        )
        ns = NewsScrapingService()
        ns.served_articles = {"http://example.com/a"}
        ns.news_data["TestSource"] = feedparser.parse(
            '<rss><channel><item><title>T</title><link>http://x</link></item></channel></rss>'
        )

        pds = PersistentDataService(data_dir=tmp)
        pds.save_all(reason="flush")

        self.assertTrue((tmp / "trade_lifecycle.snapshot").is_file())
        self.assertTrue((tmp / "news_scraper.snapshot").is_file())

        _clear_singletons()
        PersistentDataService._SHUTDOWN_SAVE_DONE = False

        TradeLifecycleManager()
        NewsScrapingService(
            rss_feeds={"TestSource": "http://example.com/feed"},
            skip_initial_scrape=True,
        )
        pds2 = PersistentDataService(data_dir=tmp)
        pds2.load_all()

        tm2 = TradeLifecycleManager()
        self.assertEqual(tm2.archived_entries, [])
        self.assertEqual(tm2._article_id_index, {})
        self.assertEqual(tm2._buy_order_id_index, {})
        self.assertEqual(tm2.ready_to_sell, [])

        ns2 = NewsScrapingService()
        self.assertEqual(ns2.served_articles, {"http://example.com/a"})
        self.assertIn("TestSource", ns2.news_data)

    def test_save_all_flush_logs_distinct_from_shutdown(self):
        tmp = Path(self._tmp)
        TradeLifecycleManager()
        NewsScrapingService(skip_initial_scrape=True)
        pds = PersistentDataService(data_dir=tmp)
        mock_log = MagicMock()
        pds._logger.log_info = mock_log
        pds.save_all(reason="flush")
        pds.save_all(reason="shutdown")
        messages = [c[0][0] for c in mock_log.call_args_list]
        self.assertTrue(any("routine flush" in m for m in messages))
        self.assertTrue(any("program termination" in m for m in messages))

    def test_shutdown_save_skips_second_call(self):
        tmp = Path(self._tmp)
        TradeLifecycleManager()
        NewsScrapingService(skip_initial_scrape=True)
        pds = PersistentDataService(data_dir=tmp)
        mock_log = MagicMock()
        pds._logger.log_info = mock_log
        pds.save_all(reason="shutdown")
        pds.save_all(reason="shutdown")
        shutdown_msgs = [c[0][0] for c in mock_log.call_args_list if "program termination" in c[0][0]]
        self.assertEqual(len(shutdown_msgs), 1)

    def test_load_all_missing_files_no_crash(self):
        tmp = Path(self._tmp)
        TradeLifecycleManager()
        NewsScrapingService(skip_initial_scrape=True)
        pds = PersistentDataService(data_dir=tmp)
        pds.load_all()


if __name__ == "__main__":
    unittest.main()
