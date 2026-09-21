import unittest
import sys
import os
from unittest.mock import patch

from src.trendline.sentiment_service import SentimentService
from src.lib.ticker_service import TickerService

_TRADABLE_FOR_TESTS = {"NVDA", "GLW", "AAPL", "MSFT", "APPL", "NVIDIA"}


def _is_tradable_test_symbol(symbol: str) -> bool:
    return symbol.upper() in _TRADABLE_FOR_TESTS


# Add src directory to path


class TestSentimentService(unittest.TestCase):
    """Unit tests for SentimentService class."""

    def setUp(self):
        patcher = patch.object(
            TickerService,
            "is_tradable_stock_symbol",
            side_effect=_is_tradable_test_symbol,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_response_matches_format_1(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            result = service._response_matches_format("[Positive] | NVDA")

            self.assertTrue(result)

    def test_response_matches_format_2(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            result = service._response_matches_format("[Neutral] | NVIDIA (NVDA)")

            self.assertTrue(result)
    def test_response_matches_format_3(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            result = service._response_matches_format("Neutral | None")

            self.assertTrue(result)
    def test_response_matches_format_4(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            result = service._response_matches_format("""[Negative] | None

Note: The article does not have an explicitly negative tone towards any company mentioned, but the overall sentiment is neutral as it discusses various companies involved in AI without expressing a clear opinion or emotion. However, there's no associated publicly traded company with a negative sentiment in this context.""")      

            self.assertTrue(result)
    def test_response_matches_format_5(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            result = service._response_matches_format("[Sentiment] | [Ticker] Neutral | NVDA")

            self.assertTrue(result)
    def test_response_matches_format_6(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            result = service._response_matches_format("Negative | NVDA")

            self.assertTrue(result)
    def test_response_matches_format_7(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            result = service._response_matches_format("Negative NVDA")

            self.assertFalse(result)


    def test_parse_response_1(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            sentiment, ticker = service._parse_response("Negative | NVDA")

            self.assertEqual(sentiment, "negative")
            self.assertEqual(ticker, "NVDA")
    def test_parse_response_2(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            sentiment, ticker = service._parse_response("[Sentiment] | [Ticker] Neutral | NVDA")

            self.assertEqual(sentiment, "sentiment")
            self.assertEqual(ticker, "Ticker Neutral | NVDA")

    def test_parse_response_3(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            sentiment, ticker = service._parse_response("[Neutral] | NVIDIA (NVDA)")

            self.assertEqual(sentiment, "neutral")
            self.assertEqual(ticker, "NVIDIA (NVDA)")

            

    def test_parse_response_4(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            sentiment, ticker = service._parse_response("""[Negative] | None

Note: The article does not have an explicitly negative tone towards any company mentioned, but the overall sentiment is neutral as it discusses various companies involved in AI without expressing a clear opinion or emotion. However, there's no associated publicly traded company with a negative sentiment in this context.""")

            self.assertEqual(sentiment, "negative")
            self.assertEqual(ticker, "None")

    def test_parse_response_5(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            sentiment, ticker = service._parse_response("Neutral | None (The article does not specifically mention a company that is publicly traded)")

            self.assertEqual(sentiment, "neutral")
            self.assertEqual(ticker, "None (The article does not specifically mention a company that is publicly traded)")

    def test_analyze_sentiment_1(self):
            """Test that batch analysis handles individual errors gracefully."""
            if os.getenv("RUN_OLLAMA_INTEGRATION_TESTS", "0").strip() in ("0", "false", "False", ""):
                self.skipTest("Requires a running local Ollama server. Set RUN_OLLAMA_INTEGRATION_TESTS=1 to enable.")
            service = SentimentService()
            
            service.analyze_sentiment(
                "NVIDIA shares soared 5% today after announcing a new Blackwell chip breakthrough.",
                "https://example.com/nvidia",
            )

if __name__ == '__main__':
    unittest.main()
