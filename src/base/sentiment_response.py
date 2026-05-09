from dataclasses import dataclass


@dataclass
class SentimentResponse:
    """
    Data class representing the response from sentiment analysis.

    Attributes:
        sentiment (str): The sentiment classification (positive, neutral, or negative).
        ticker (str): Comma-separated US equity tickers with no spaces (e.g. "NVDA,GLW"), or "NONE".
        format_match (bool): Whether the LLM response matched the expected format.
        ticker_found (bool): Whether at least one valid tradable ticker was found.
        raw_response (str): The raw, unprocessed response from the LLM.
    """

    sentiment: str
    ticker: str
    format_match: bool
    ticker_found: bool
    raw_response: str

    def get_ticker_list(self) -> list[str]:
        """Parse ``ticker`` into individual symbols; empty if NONE or invalid."""
        if not self.ticker or self.ticker.upper() == "NONE":
            return []
        out: list[str] = []
        for part in self.ticker.split(","):
            s = part.strip().upper()
            if not s or s == "NONE":
                continue
            if s not in out:
                out.append(s)
        return out
