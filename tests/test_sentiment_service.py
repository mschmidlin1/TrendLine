import unittest
import sys
import os
from src.sentiment_service import SentimentResponse, SentimentService
# Add src directory to path



class TestSentimentService(unittest.TestCase):
    """Unit tests for SentimentService class."""

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
            self.assertEqual(ticker, "TICKER")

    def test_parse_response_3(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            sentiment, ticker = service._parse_response("[Neutral] | NVIDIA (NVDA)")

            self.assertEqual(sentiment, "neutral")
            self.assertEqual(ticker, "NVIDIA")

            

    def test_parse_response_4(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            sentiment, ticker = service._parse_response("""[Negative] | None

Note: The article does not have an explicitly negative tone towards any company mentioned, but the overall sentiment is neutral as it discusses various companies involved in AI without expressing a clear opinion or emotion. However, there's no associated publicly traded company with a negative sentiment in this context.""")

            self.assertEqual(sentiment, "negative")
            self.assertEqual(ticker, "NONE")

    def test_parse_response_5(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            sentiment, ticker = service._parse_response("Neutral | None (The article does not specifically mention a company that is publicly traded)")

            self.assertEqual(sentiment, "neutral")
            self.assertEqual(ticker, "NONE")
    def test_parse_sentiment_1(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            test_response = service._parse_sentiment("Neutral | None (The article does not specifically mention a company that is publicly traded)")

            true_response = SentimentResponse("neutral", "NONE", format_match=True, ticker_found=False, raw_response="")
            self.assertEqual(true_response.sentiment, test_response.sentiment)
            self.assertEqual(true_response.ticker, test_response.ticker)
            self.assertEqual(true_response.format_match, test_response.format_match)
            self.assertEqual(true_response.ticker_found, test_response.ticker_found)
    def test_parse_sentiment_2(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            test_response = service._parse_sentiment("[Neutral] | NVIDIA (NVDA)")

            true_response = SentimentResponse("neutral", "NVIDIA", format_match=True, ticker_found=False, raw_response="")
            self.assertEqual(true_response.sentiment, test_response.sentiment)
            self.assertEqual(true_response.ticker, test_response.ticker)
            self.assertEqual(true_response.format_match, test_response.format_match)
            self.assertEqual(true_response.ticker_found, test_response.ticker_found)
    def test_parse_sentiment_3(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            test_response = service._parse_sentiment("[Neutral]  NVIDIA (NVDA)")

            true_response = SentimentResponse("", "", format_match=False, ticker_found=False, raw_response="")
            self.assertEqual(true_response.sentiment, test_response.sentiment)
            self.assertEqual(true_response.ticker, test_response.ticker)
            self.assertEqual(true_response.format_match, test_response.format_match)
            self.assertEqual(true_response.ticker_found, test_response.ticker_found)

    def test_parse_sentiment_4(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            test_response = service._parse_sentiment("[Sentiment] | [Ticker] Neutral | NVDA")

            true_response = SentimentResponse("sentiment", "TICKER", format_match=False, ticker_found=False, raw_response="")
            self.assertEqual(true_response.sentiment, test_response.sentiment)
            self.assertEqual(true_response.ticker, test_response.ticker)
            self.assertEqual(true_response.format_match, test_response.format_match)
            self.assertEqual(true_response.ticker_found, test_response.ticker_found)

    def test_parse_sentiment_5(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            test_response = service._parse_sentiment("Positive | APPL")

            true_response = SentimentResponse("positive", "APPL", format_match=True, ticker_found=False, raw_response="")
            self.assertEqual(true_response.sentiment, test_response.sentiment)
            self.assertEqual(true_response.ticker, test_response.ticker)
            self.assertEqual(true_response.format_match, test_response.format_match)
            self.assertEqual(true_response.ticker_found, test_response.ticker_found)

    def test_analyze_sentiment_1(self):
            """Test that batch analysis handles individual errors gracefully."""
            service = SentimentService()
            
            test_response = service.analyze_sentiment("NVIDIA shares soared 5% today after announcing a new Blackwell chip breakthrough.")

            #true_response = SentimentResponse("positive", "NVDA", format_match=True, ticker_found=True, raw_response="")
            if test_response.ticker == "NVDA":
                self.assertTrue(test_response.ticker_found)

if __name__ == '__main__':
    unittest.main()
