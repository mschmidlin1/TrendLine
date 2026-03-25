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
		# Assert that update returns a boolean (could be True or False depending on feed updates)
		self.assertIsInstance(changes, bool)
	
	def test_get_unserved_articles_returns_tuples(self):
		"""Test that get_unserved_articles returns list of tuples with correct structure"""
		service = NewsScrapingService()
		articles = service.get_unserved_articles()
		
		# Verify return type is list
		self.assertIsInstance(articles, list)
		
		if len(articles) > 0:
			# Verify each item is a tuple with 2 elements
			for item in articles:
				self.assertIsInstance(item, tuple)
				self.assertEqual(len(item), 2)
				
				# First element should be string (source name)
				source_name, entry = item
				self.assertIsInstance(source_name, str)
				
				# Second element should be dict (entry data)
				self.assertIsInstance(entry, dict)
	
	def test_get_unserved_articles_marks_as_served(self):
		"""Test that get_unserved_articles automatically marks articles as served"""
		service = NewsScrapingService()
		
		# Get first batch of articles
		first_batch = service.get_unserved_articles()
		
		if len(first_batch) > 0:
			# Store article links from first batch
			first_batch_links = [entry.get('link') for source, entry in first_batch]
			
			# Get second batch
			second_batch = service.get_unserved_articles()
			second_batch_links = [entry.get('link') for source, entry in second_batch]
			
			# Assert no articles from first batch appear in second batch
			for link in first_batch_links:
				self.assertNotIn(link, second_batch_links)
				
				# Verify using is_article_served
				self.assertTrue(service.is_article_served(link))
	
	def test_is_article_served(self):
		"""Test that is_article_served correctly identifies served articles"""
		service = NewsScrapingService()
		
		# Get unserved articles
		articles = service.get_unserved_articles()
		
		if len(articles) > 0:
			# Extract a link from returned articles
			source, entry = articles[0]
			link = entry.get('link')
			
			# Assert is_article_served returns True for served article
			self.assertTrue(service.is_article_served(link))
			
			# Assert is_article_served returns False for fake URL
			self.assertFalse(service.is_article_served("https://fake-url-that-does-not-exist.com"))
	
	def test_reset_served_articles(self):
		"""Test that reset_served_articles clears tracking"""
		service = NewsScrapingService()
		
		# Get unserved articles (marks them as served)
		first_batch = service.get_unserved_articles()
		first_count = len(first_batch)
		
		# Reset served articles
		service.reset_served_articles()
		
		# Get unserved articles again
		second_batch = service.get_unserved_articles()
		second_count = len(second_batch)
		
		# Assert same count or more articles are available after reset
		self.assertGreaterEqual(second_count, first_count)
	
	def test_no_duplicate_articles_served(self):
		"""Test that articles are served exactly once (idempotency)"""
		service = NewsScrapingService()
		
		# Collect all article links from multiple calls
		all_links = []
		
		# Call get_unserved_articles multiple times
		for _ in range(3):
			articles = service.get_unserved_articles()
			links = [entry.get('link') for source, entry in articles]
			all_links.extend(links)
		
		# Assert no duplicate links
		self.assertEqual(len(all_links), len(set(all_links)))
	
	def test_update_provides_new_articles(self):
		"""Test that update method returns correct boolean"""
		service = NewsScrapingService()
		
		# Get all unserved articles (exhausts current articles)
		service.get_unserved_articles()
		
		# Call update
		updated = service.update()
		
		# Assert update returns a boolean
		self.assertIsInstance(updated, bool)
	
	def test_article_id_generation(self):
		"""Test that article ID extraction works correctly"""
		service = NewsScrapingService()
		
		# Get unserved articles
		articles = service.get_unserved_articles()
		
		# For each article, verify entry has 'link' field
		for source, entry in articles:
			self.assertIn('link', entry)
			link = entry.get('link')
			
			# Verify link is non-empty string
			self.assertIsInstance(link, str)
			self.assertGreater(len(link), 0)