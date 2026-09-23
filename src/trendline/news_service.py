import pandas as pd
import numpy as np
import datetime
from datetime import datetime, timezone
import os
from trend_core.configs import RSS_FEED_URLS
from trend_core.base.singleton import SingletonMeta
import feedparser
from typing import List, Dict, Tuple, Any
from trend_core.base.tl_logger import LoggingService
from feedparser.util import FeedParserDict
from trend_core.database.db_service import DatabaseService
from psycopg.types.json import Jsonb
import json
from time import struct_time
from dataclasses import dataclass

@dataclass(frozen=True)
class PendingSentimentAnalysis:
    article_id: str
    title: str

class NewsScrapingService(metaclass=SingletonMeta):
    def __init__(self, rss_feeds: Dict[str, str] = RSS_FEED_URLS, skip_initial_scrape: bool = False):
        self._logger = LoggingService()
        self.rss_feeds: Dict[str, str] = rss_feeds
        if skip_initial_scrape:
            self.news_data = {name: feedparser.parse('') for name in self.rss_feeds}
        else:
            self.news_data = self._initial_scrape()
        self._logger.log_info("Scraping service initialized")
        self.db_service = DatabaseService()

    def _initial_scrape(self) -> Dict[str, FeedParserDict]:
        """
        Scrapes the news using the `self.rss_feeds` and returns the data.

        Returns:
        Dict[source name: data]
        """
        news_data = dict()
        for name, url in self.rss_feeds.items():
            news_data[name] = self._scrape_rss_feed(url)
            if getattr(news_data[name], 'status') != 200:
                self._logger.log_warning(f"When doing first scraping, unexpected status: {getattr(news_data[name], 'status')} ----- {url}")
        return news_data


    # def get_persistent_snapshot(self) -> Dict[str, Any]:
    #     """Return in-memory state to be persisted across restarts."""
    #     return {
    #         'rss_feeds': self.rss_feeds,
    #         'served_articles': self.served_articles,
    #         'news_data': self.news_data,
    #     }

    # def restore_from_persistent_snapshot(self, snapshot: Dict[str, Any]) -> None:
    #     """Restore state from :meth:`get_persistent_snapshot`."""
    #     for key in ('rss_feeds', 'served_articles', 'news_data'):
    #         if key not in snapshot:
    #             raise ValueError(f"Invalid persistent snapshot: missing '{key}'")
    #     self.rss_feeds = snapshot['rss_feeds']
    #     self.served_articles = snapshot['served_articles']
    #     self.news_data = snapshot['news_data']

    def update(self) -> bool:
        """
        Updates the scraping for all the rss feeds.

        Returns True if any of the rss feeds were updated.
        """
        new_data = False
        for name in self.rss_feeds.keys():
            url = self.rss_feeds[name]
            feed = self.news_data[name]
            (new, new_feed) = self._check_for_new(url, feed)
            if new and new_feed:
                self.news_data[name] = new_feed
                new_data = True
        return new_data

    def _check_for_new(self, url: str, feed: FeedParserDict) -> Tuple[bool, FeedParserDict | None]:
        """
        Checks for updated rss feed for a specific URL.
        If it's updated, returns the new FeedParserDict.
        Returns:
        (if the feedparser dict was updated, either previous or new feedparser dict)
        """
        # Use .get() with a default of None to be safe
        last_etag = feed.get('etag') if feed else None
        last_modified = feed.get('modified') if feed else None

        new_feed = self._scrape_rss_feed(url, etag=last_etag, modified=last_modified)
        
        # Check if the server explicitly said "nothing changed"
        if getattr(new_feed, 'status', None) == 304:
            return (False, feed)
            
        # Check if we got a successful update
        if getattr(new_feed, 'status', None) == 200:
            return (True, new_feed)

        # Fallback: If there's a 404, 500, or connection error, 
        # return False and the original feed so the app doesn't break.
        self._logger.log_warning(f"Unexpected return status {str(getattr(new_feed, 'status', None))} from feedparser for {url}")
        return (False, feed)

    def _scrape_rss_feed(self, rss_url: str, **kwargs) -> FeedParserDict | None:
        """
        Scrape news from RSS feed instead of web scraping.
        More reliable and respectful of website policies.
        
        Parameters:
        -----------
        rss_url: str - URL of the RSS feed
        
        Returns:
        --------
        FeedParserDict
        """
        try:
            feed: FeedParserDict = feedparser.parse(rss_url, **kwargs)
            return feed
        except Exception as e:
            self._logger.log_error(f"RSS scrape failed for {rss_url} with error {e}")
            return None
    
    def get_new_articles(self) -> list[PendingSentimentAnalysis]:
        """
        Retrieve unserved articles and automatically mark them as served.
        
        Returns:
        --------
        List[Tuple[str, dict]] - List of tuples (source_name, entry_dict)
        """
        unserved = []
        served_article_ids = self._get_served_article_ids()
        # Collect all unserved articles from all feeds
        for source_name, feed in self.news_data.items():
            if feed and hasattr(feed, 'entries'):
                for entry in feed.entries:
                    article_id = entry.get('link', '')
                    if article_id and article_id not in served_article_ids:
                        unserved.append((source_name, entry, article_id))
        
        # Sort by published date descending (newest first)
        def get_published_date(item):
            entry = item[1]
            date_str = entry.get('published', entry.get('updated', ''))
            try:
                # Convert to timezone-naive to avoid comparison issues
                dt = pd.to_datetime(date_str)
                if dt.tz is not None:
                    dt = dt.tz_localize(None)
                return dt
            except:
                return pd.Timestamp.min
        
        unserved.sort(key=get_published_date, reverse=True)
        
        # Mark all returned articles as served
        for source_name, entry, article_id in unserved:
            self._archive_article(source_name, entry)
        
        # Return without article_id (just source_name and entry)
        return self._get_unserved_articles()

    def _get_unserved_articles(self) -> list[PendingSentimentAnalysis]:
        rows = self.db_service.fetch_all(
            """
            SELECT article_id, title FROM articles
            WHERE sentiment_analyzed_at IS NULL
            """)
        return [PendingSentimentAnalysis(row[0], row[1]) for row in rows]

    def _get_served_article_ids(self) -> List[str]:
        rows = self.db_service.fetch_all(
            """
            SELECT article_id FROM articles
            WHERE sentiment_analyzed_at IS NOT NULL
            """)
        return [row[0] for row in rows]

    def _archive_article(self, source: str, article: FeedParserDict):

        article_dict = {}
        article_dict["article_id"] = article.get('link')
        row = self.db_service.fetch_one(
            "SELECT id FROM news_sources WHERE url = %s",
            (self.rss_feeds[source],),
        )
        source_id = row[0] if row else None
        article_dict["source_id"] = source_id
        article_dict["title"] = article.get('title', '')
        article_dict["summary"] = article.get('summary', '')
        parsed = article.get("published_parsed")
        if isinstance(parsed, struct_time):
            article_dict["published_at"] = datetime(
                parsed.tm_year,
                parsed.tm_mon,
                parsed.tm_mday,
                parsed.tm_hour,
                parsed.tm_min,
                parsed.tm_sec,
                tzinfo=timezone.utc,
            )
        else:
            article_dict["published_at"] = None
        article_dict["published_raw"] = article.get('published', '')
        article_dict["rss_guid"] = article.get('id')
        article_dict["raw_entry"] = Jsonb(json.loads(json.dumps(dict(article), default=str)))
        article_dict["archived_at"] = datetime.now(timezone.utc)
        article_dict["sentiment_analyzed_at"] = None
        article_dict["resulted_in_purchase"] = False
        article_dict["sentiment_raw_response"] = None
        article_dict["sentiment_format_match"] = None

        self.db_service.insert_row_dict("articles", article_dict)
