from src.base.singleton import SingletonMeta
from src.base.sentiment_response import SentimentResponse
import ollama
from src.base.timer import Timer
import ollama
import re
from typing import Tuple, List
from src.base.tl_logger import LoggingService
from src.ticker_service import TickerService

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
        
        timer = Timer()
        timer.start()
        full_response: ollama.ChatResponse = ollama.chat(
            model='llama3.1',
            messages=[
                {'role': 'system', 'content': self.instructions}, # The Rules
                {'role': 'user', 'content': text},        # The Data
            ]
        )
        timer.stop()
        ellapsed_time = timer.elapsed_str()
        self._logger.log_info(f"Sentiment predicted by ollama. Took {ellapsed_time}")

        response = full_response['message']['content']
        return self._parse_sentiment(response)

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


        
    
    
