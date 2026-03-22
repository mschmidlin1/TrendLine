from newspaper import Article
import newspaper
import pandas as pd
import numpy as np
import datetime
import os
from src.configs import RSS_FEED_URLS
from src.singleton import SingletonMeta
import feedparser
from feedsearch import search
from typing import List, Dict, Tuple
from src.tl_logger import LoggingService
from feedparser.util import FeedParserDict

class NewsScrapingService(metaclass=SingletonMeta):
    def __init__(self, rss_feeds: List[str] = RSS_FEED_URLS):
        self.logger = LoggingService()
        self.rss_feeds: Dict[str, str] = rss_feeds
        self.news_data: Dict[str, FeedParserDict] = self.scrape_news()
        self.logger.log_info("Scraping service initialized")

    def scrape_news(self) -> Dict[str, FeedParserDict]:
        """
        Scrapes the news using the `self.rss_feeds` and returns the data.

        Returns:
        Dict[source name: data]
        """
        news_data = dict()
        for name, url in self.rss_feeds.items():
            news_data[name] = self._scrape_rss_feed(url)
            if getattr(news_data[name], 'status') != 200:
                self.logger.log_warning(f"When doing first scraping, unexpected status: {getattr(news_data[name], 'status')} ----- {url}")
        return news_data
    
    def check_for_new(self, url: str, feed: FeedParserDict) -> Tuple[bool, FeedParserDict]:
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
        self.logger.log_warning(f"Unexpected return status {str(getattr(new_feed, 'status', None))} from feedparser for {url}")
        return (False, feed)

    def update(self) -> bool:
        """
        Updates the scraping for all the rss feeds.

        Returns True if any of the rss feeds were updated.
        """
        new_data = False
        for name in self.rss_feeds.keys():
            url = self.rss_feeds[name]
            feed = self.news_data[name]
            (new, new_feed) = self.check_for_new(url, feed)
            if new:
                self.news_data[name] = new_feed
                new_data = True

    def _scrape_rss_feed(self, rss_url: str, **kwargs) -> FeedParserDict:
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
            self.logger.log_error(f"RSS scrape failed for {rss_url} with error {e}")
            return None
            

    





