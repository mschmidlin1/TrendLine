from src.base.singleton import SingletonMeta
from src.base.sentiment_response import SentimentResponse
from src.base.timer import Timer
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
        You are a news analyst. For every headline/section provided:
        1. Rate the 'Sentiment' as Positive, Neutral, or Negative.
        3. Extract the main 'Company' mentioned and reply with the ticker symbol of the company. If there is no associated publicly traded company, reply with "None" for the ticker.
        Response Format: [Sentiment] | [Ticker]
        """
        self._logger = LoggingService()
        self._ticker_service: TickerService = TickerService()
    
    def analyze_sentiment(self, text: str) -> SentimentResponse:
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
        
        attempts = max(1, int(OLLAMA_MAX_ATTEMPTS))
        last_error: Optional[Exception] = None

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
                        {"role": "user", "content": text},  # The Data
                    ],
                    **kwargs,
                )
                timer.stop()
                ellapsed_time = timer.elapsed_str()
                self._logger.log_info(f"Sentiment predicted by ollama. Took {ellapsed_time}")

                response = full_response["message"]["content"]
                return self._parse_sentiment(response)
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

                # Final attempt failed: log error and return safe non-actionable response.
                self._logger.log_error(
                    f"Ollama sentiment attempt {attempt}/{attempts} failed: {type(e).__name__}: {e}. Returning non-actionable SentimentResponse."
                )
                raw = f"OllamaError: {type(last_error).__name__}: {last_error}" if last_error else "OllamaError"
                # Ensure caller cannot act on this response
                return SentimentResponse("", "NONE", format_match=False, ticker_found=False, raw_response=raw)

        # Should be unreachable, but keep a safe default.
        return SentimentResponse("", "NONE", format_match=False, ticker_found=False, raw_response="OllamaError")

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

    def _parse_sentiment(self, response: str) -> SentimentResponse:
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
        try:
            format_match = self._response_matches_format(response)
            sentiment: str = ""
            ticker: str = ""
            if format_match:
                sentiment, ticker = self._parse_response(response)
            ticker_found = True
            if ticker.upper() == "NONE":
                ticker_found = False
            if ticker=="":
                ticker_found = False
            if not self._ticker_service.is_tradable_stock_symbol(ticker):
                ticker_found = False
            if sentiment not in ['positive', 'neutral', 'negative']:
                format_match = False
                sentiment = "NONE"
        except:
            self._logger.log_error(f"SentimentService errored when trying to parse this response: '{response}'")
            format_match = False
            ticker_found = False
            sentiment = ""
            ticker = ""
        #unify responses for presentation
        if not ticker_found:
            ticker = "NONE"
        return SentimentResponse(sentiment, ticker, format_match, ticker_found, response)

    def _parse_response(self, response) -> Tuple[str, str]:
        """
        Extract and clean sentiment and ticker data from the LLM response string.
        
        Parses a pipe-delimited response in the format "[Sentiment] | [Ticker]" or
        "Sentiment | Ticker", performing extensive string cleaning and normalization:
        - Splits on the pipe delimiter
        - Removes brackets, extra whitespace, and formatting characters
        - Converts sentiment to lowercase for consistency
        - Converts ticker to uppercase for standard stock symbol format
        
        Args:
            response (str): The raw LLM response string to parse.
            
        Returns:
            Tuple[str, str]: A tuple containing (sentiment, ticker) where:
                - sentiment: Lowercase string (e.g., "positive", "neutral", "negative")
                - ticker: Uppercase stock symbol (e.g., "AAPL", "TSLA", "NONE")
        """

        split_response: List[str] = response.split("|")

        #parse sentiment
        sentiment, ticker = split_response[0], split_response[1]
        sentiment = sentiment.split()[0]
        sentiment = sentiment.strip()
        sentiment = sentiment.lower()
        sentiment = sentiment.replace("[", "")
        sentiment = sentiment.replace("]", "")

        #parse ticker
        ticker = ticker.lstrip()
        ticker = ticker.split()[0]
        ticker = ticker.replace("[", "")
        ticker = ticker.replace("]", "")
        ticker = ticker.upper()

        return (sentiment, ticker)
    
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
        # ^\s*                      - Start of string, optional whitespace
        # (?:\[([^\]]+)\]|([^\|]+)) - Either [text] or text without pipe
        # \s*\|\s*                  - Pipe separator with optional whitespace
        # ([\s\S]+)                 - Text after pipe - captures everything to group 3
        #                           -   [\s\S] means "any whitespace OR any non-whitespace"
        #                           -   This effectively matches ANY character including newlines
        #                           -   No flag needed - works in all regex modes
        # $                         - End of string

    
        pattern = pattern = r'^\s*(?:\[([^\]]+)\]|([^\|]+))\s*\|\s*([\s\S]+)$'
        match = re.match(pattern, text)
        return match is not None


        
    
    
