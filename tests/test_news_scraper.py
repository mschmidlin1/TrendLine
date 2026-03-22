import unittest
from src.news_scraper import NewsScrapingService
from src.converters import feedparser_to_df


class TestNewsScraper(unittest.TestCase):
	"""Unit tests for NewsScrapingService class."""

	def test_constructor(self):
		service = NewsScrapingService()
		print(service.rss_feeds)

	def test_df_converter(self):
		service = NewsScrapingService()
		for name, feed in service.news_data.items():

			df = feedparser_to_df(feed)
			print(name)
			print(df.shape)
			print(df["headline"])
	
	def test_update(self):
		service = NewsScrapingService()
		changes = service.update()
		self.assertFalse(changes)#asserting false here because we just scraped all the data so it seems REALLY unlikely something would have changed in that short of time