from datetime import datetime, timezone
from src.base.singleton import SingletonMeta
from feedparser.util import FeedParserDict
from src.base.timer import Timer
from src.database.db_service import DatabaseService
import re
from typing import Tuple, List, Optional, TYPE_CHECKING
import time
from src.base.tl_logger import LoggingService
from src.ticker_service import TickerService
from src.configs import (
    OLLAMA_MODEL,
    OLLAMA_MAX_ATTEMPTS,
    OLLAMA_RETRY_BACKOFF_SECONDS,
    OLLAMA_TIMEOUT_SECONDS,
)

if TYPE_CHECKING:
    import ollama  # pragma: no cover

class SentimentService(metaclass=SingletonMeta):
    """
    Singleton service for analyzing sentiment of financial news using LLM.
    
    This service uses the Ollama LLM (llama3.1 model) to analyze financial news headlines
    and articles, determining both the sentiment (positive, neutral, or negative) and
    extracting the relevant stock ticker symbol mentioned in the text.
    
    Sentiment interpretations:
        - Positive: Indicates a potential buy signal for the stock
        - Neutral: No clear directional signal
        - Negative: Indicates a potential sell signal for the stock
    
    The service implements the Singleton pattern to ensure only one instance exists,
    optimizing resource usage and maintaining consistent state across the application.
    
    Attributes:
        instructions (str): System prompt that guides the LLM's analysis behavior.
        logger (LoggingService): Logger instance for tracking operations and errors.
    """
    def __init__(self):
        """
        Initialize the SentimentService with instructions for the LLM and logging service.
        
        Sets up the system prompt that guides the LLM to analyze financial news sentiment
        and extract company ticker symbols from text.
        """
        self.instructions = """
        You are a news analyst. For every headline or text segment provided:

        1. Identify every distinct publicly traded US company that the text clearly refers to (by name or unambiguous context). For each, respond with its standard US equity ticker symbol. You must include all such companies—not only the single "main" company.

        2. Rate the Sentiment for each distinct publicly traded US company as Positive, Neutral, or Negative. Each company gets it's own sentiment. Each sentiment should correspond to how that specific stock is expected to do.

            - Important: only give positive sentiment to headlines/tickers which indicate **future** promise. A headline like "Apple stock soared yesterday" doesn't indicate future promise it's indicating that Apple's stock went up yesterday so it would get "Neutral" sentiment.
            - Important: The number of companies must equal the number of sentiments.

        3. After the pipe, output the ticker field as follows:
           - If there is at least one such company: a single comma-separated list of tickers with NO spaces after any comma (correct: NVDA,GLW,AAPL — incorrect: NVDA, GLW).
           - List tickers in order of prominence in the text (the company most central or first-mentioned first). If the same company appears multiple times, include that ticker only once.
           - If there is no clearly referenced publicly traded US company: the literal None (meaning no tickers).

        Response format (one line):
        [Sentiments] | [TickerField]

        Sentiments is at least on instance of [Positive, Negative, Neutral] seperated by comas with no spaces.
        TickerField is either None, one ticker, or multiple tickers separated by commas with no spaces.

        Examples:
        Positive,Negative | NVDA,GLW
        Neutral | AAPL
        Negative | None
        """
        self._logger = LoggingService()
        self._ticker_service: TickerService = TickerService()
        self._db_service = DatabaseService()
    
    def archive_no_title(self, article_id: str):
        """Update articles table for article with no title."""
        self._db_service.execute(
            """
            UPDATE articles
            SET sentiment_analyzed_at = %s,
                sentiment_raw_response = %s,
                sentiment_format_match = %s
            WHERE article_id = %s
            """,
            (
                datetime.now(timezone.utc),
                None,
                False,
                article_id,
            ),
        )
    
    def analyze_sentiment(self, text: str, article_id: str) -> None:
        """
        Analyze the sentiment of financial news text using an LLM.
        
        This method sends the provided text to the Ollama LLM (llama3.1 model) along with
        system instructions to determine sentiment and extract the relevant stock ticker.
        
        Args:
            text (str): The financial news headline or text to analyze.
            
        Returns:
            SentimentResponse: A dataclass containing the sentiment classification, ticker symbol,
                             format validation flags, and the raw LLM response.
        """

        if not isinstance(article_id, str) or not article_id:
            raise TypeError("article ID must be a non-empty string")
        response = self._get_model_response(text)
        if response is None:
            self._db_service.execute(
                """
                UPDATE articles
                SET sentiment_analyzed_at = %s,
                    sentiment_raw_response = %s,
                    sentiment_format_match = %s
                WHERE article_id = %s
                """,
                (
                    datetime.now(timezone.utc),
                    None,
                    False,
                    article_id,
                ),
            )
            return
        format_match = self._parse_sentiment(response, article_id)

        self._db_service.execute(
            """
            UPDATE articles
            SET sentiment_analyzed_at = %s,
                sentiment_raw_response = %s,
                sentiment_format_match = %s
            WHERE article_id = %s
            """,
            (
                datetime.now(timezone.utc),
                response,
                format_match,
                article_id,
            ),
        )

    def _get_model_response(self, headline: str) -> str | None:
        """
        Calls the ollama model and gets the response.
        """
        attempts = max(1, int(OLLAMA_MAX_ATTEMPTS))
        last_error: Optional[Exception] = None
        response = None
        for attempt in range(1, attempts + 1):
            timer = Timer()
            timer.start()
            try:
                import ollama

                kwargs = {}
                if OLLAMA_TIMEOUT_SECONDS is not None:
                    kwargs["timeout"] = OLLAMA_TIMEOUT_SECONDS

                full_response = ollama.chat(
                    model=OLLAMA_MODEL,
                    messages=[
                        {"role": "system", "content": self.instructions},  # The Rules
                        {"role": "user", "content": headline},  # The Data
                    ],
                    **kwargs,
                )
                timer.stop()
                ellapsed_time = timer.elapsed_str()
                self._logger.log_info(f"Sentiment predicted by ollama. Took {ellapsed_time}")

                response = full_response["message"]["content"]
                return response

            except Exception as e:
                timer.stop()
                last_error = e
                if attempt < attempts:
                    self._logger.log_warning(
                        f"Ollama sentiment attempt {attempt}/{attempts} failed: {type(e).__name__}: {e}. Retrying."
                    )
                    backoff = float(OLLAMA_RETRY_BACKOFF_SECONDS) * (2 ** (attempt - 1))
                    time.sleep(max(0.0, backoff))
                    continue

                
                self._logger.log_error(
                    f"Ollama sentiment attempt {attempt}/{attempts} failed: {type(e).__name__}: {e}."
                )
                
            return response  
                
    def warmup(self) -> bool:
        """
        Best-effort warmup. Never raises; returns True on success.
        """
        try:
            import ollama

            kwargs = {}
            if OLLAMA_TIMEOUT_SECONDS is not None:
                kwargs["timeout"] = OLLAMA_TIMEOUT_SECONDS
            ollama.chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": "Reply with: OK"},
                    {"role": "user", "content": "ping"},
                ],
                **kwargs,
            )
            return True
        except Exception as e:
            self._logger.log_warning(f"Ollama warmup failed: {type(e).__name__}: {e}")
            return False

    def _parse_sentiment(self, response: str, article_id: str) -> bool:
        """
        Parse the raw LLM response into a structured SentimentResponse object.
        
        Validates the response format, extracts sentiment and ticker information,
        and handles any parsing errors gracefully.
        
        Args:
            response (str): The raw response string from the LLM.
            
        Returns:
            SentimentResponse: A structured response object with parsed sentiment data
                             and validation flags indicating parsing success.
                        
        """
        if not self._response_matches_format(response):
            return False
        sentiments, tickers = self._parse_response(response)
        if len(sentiments) != len(tickers):
            self._logger.log_error(f"Sentiment/ticker count mismatch: {response!r}")
            return False
        if len(sentiments) == 1 and sentiments[0].lower()=="none":
            return True
        if tickers == ["NONE"]:
            return True
        ticker_validities = self._validate_tickers(tickers)
        sentiment_validities = self._validate_sentiments(sentiments)
        try:
            for i, (sentiment, ticker) in enumerate(zip(sentiments, tickers)):
                if not sentiment_validities[i]:
                    sentiment = "NONE"
                self._db_service.insert_row_dict("sentiments", {
                    "article_id": article_id,
                    "ticker": ticker,
                    "company": self._ticker_service.lookup_stock_name(ticker) if ticker_validities[i] else None,
                    "sentiment": sentiment,
                    "ticker_valid": ticker_validities[i],
                    "ordinal": i,
                    "created_at": datetime.now(timezone.utc),
                })
        except Exception as e:
            self._logger.log_error(f"Failed inserting sentiments for {article_id}: {e}")
            return False
        return True

    def _validate_tickers(self, tickers: List[str]) -> List[bool]:
        """
        Validate each ticker using ticker service.
        """
        validities = []
        for ticker in tickers:
            if ticker == "" or ticker.upper()=="NONE":
                validities.append(False)
                continue
            validities.append(self._ticker_service.is_tradable_stock_symbol(ticker))

        return validities

    def _validate_sentiments(self, sentiments: List[str]) -> List[bool]:
        """
        Validate each sentiment using accepted responses
        """
        validities = []
        for sentiment in sentiments:
            validities.append(sentiment in ['positive', 'neutral', 'negative'])
        return validities
    
    def _parse_response(self, response) -> Tuple[List[str], List[str]]:
        """
        Extract sentiment and raw ticker field (may be comma-separated) from the LLM response.
        Tradability is applied in _validate_and_join_tickers.
        """
        parts: List[str] = response.split("|", 1)
        if len(parts) < 2:
            return ([], [])

        sentiment_part = parts[0]
        ticker_part = parts[1]

        sentiment_part = sentiment_part.strip().split("\n", 1)[0].strip()
        sentiment_part = sentiment_part.lower()
        sentiment_part = sentiment_part.replace("[", "")
        sentiment_part = sentiment_part.replace("]", "")

        # First line only — models often append explanation after a newline.
        ticker_part = ticker_part.strip().split("\n", 1)[0].strip()
        ticker_part = ticker_part.replace("[", "")
        ticker_part = ticker_part.replace("]", "")


        sentiments = [s.strip() for s in sentiment_part.split(",") if s.strip()]
        tickers = [t.strip().upper() for t in ticker_part.split(",") if t.strip()]
        return (sentiments, tickers)
    
    def _response_matches_format(self, text) -> bool:
        """
        Validate whether the LLM response matches the expected format.
        
        The expected format is: [Sentiment] | [Ticker] or Sentiment | Ticker
        Uses regex pattern matching to verify the response structure.
        
        Args:
            text (str): The response text to validate.
            
        Returns:
            bool: True if the text matches the expected format, False otherwise.
        """
        # ^\s*                                 - Start of string, optional whitespace
        # \[?                                  - Optional opening bracket
        # ([A-Za-z]+                           - First sentiment token (letters only)
        #   (?:\s*,\s*[A-Za-z]+)*)             - Optional extra sentiments, comma-separated
        #                                      -   \s* around commas allows "Positive,Negative"
        #                                      -   or "Positive, Negative"
        # \]?                                  - Optional closing bracket
        # \s*\|\s*                             - Pipe separator with optional whitespace
        # ([\s\S]+)                            - Ticker field - captures everything to group 2
        #                                      -   [\s\S] means "any whitespace OR any non-whitespace"
        #                                      -   This effectively matches ANY character including newlines
        # $                                    - End of string

    
        pattern = pattern = r'^\s*\[?([A-Za-z]+(?:\s*,\s*[A-Za-z]+)*)\]?\s*\|\s*([\s\S]+)$'
        match = re.match(pattern, text)
        return match is not None


        
    
    
