from dataclasses import dataclass
from typing import List

@dataclass
class SentimentResponse:
    """
    Data class representing the response from sentiment analysis.

    Attributes:
        sentiment (List[str]): Comma seperated sentiment classification (positive, neutral, or negative).
        ticker (List[str]): Comma-separated US equity tickers with no spaces (e.g. "NVDA,GLW"), or "NONE".
        format_match (bool): Whether the LLM response matched the expected format.
        ticker_found (bool): Whether at least one valid tradable ticker was found.
        raw_response (str): The raw, unprocessed response from the LLM.
    """

    sentiments: List[str]
    tickers: List[str]
    format_match: bool
    ticker_found: bool
    raw_response: str
