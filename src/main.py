from timing_service import TimingService
import time
from news_scraper import scrape_websites
from configs import NEWS_URLS
from ticker_service import TickerService
from sentiment_service import SentimentService





timing_service = TimingService()


while True:

    #check if it's time to run another loop.
    #if it's not time, we can probably sleep until it's time
    time_seconds = timing_service.time_until_next_scrape()
    time.sleep(time_seconds+1)#sleep for one second extra so we are for sure in the next scrape period

    #scrape articles from news sources defined in configs
    articles = scrape_websites(news_urls=NEWS_URLS)#this function needs to be change so that it gets the names of the urls without needing to pass them in

    #process each article or article title for sentiment. Add a column in the pandas DF for sentiment for each article
    SentimentService.process(articles)

    #process each article or article title to find the company name and ticker symbol. Add 2 columns in the DF, one for ticker, the other for company name.
    #if there is no applicable company name, fill this column with nan
    TickerService.process(articles)

    
