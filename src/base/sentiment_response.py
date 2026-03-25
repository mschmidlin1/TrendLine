from dataclasses import dataclass

@dataclass
class SentimentResponse:
    """
    Data class representing the response from sentiment analysis.
    
    Attributes:
        sentiment (str): The sentiment classification (positive, neutral, or negative).
        ticker (str): The stock ticker symbol extracted from the text.
        format_match (bool): Whether the LLM response matched the expected format.
        ticker_found (bool): Whether a valid ticker symbol was found in the response.
        raw_response (str): The raw, unprocessed response from the LLM.
    """
    sentiment: str
    ticker: str
    format_match: bool
    ticker_found: bool
    raw_response: str
