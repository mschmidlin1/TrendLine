from newspaper import Article
import newspaper
import pandas as pd
import numpy as np
import datetime
import os
from configs import set_logger
set_logger()







def scrape_news_website(website_url):
    """
    Scrapes a single news website for articles using the newspaper library. https://newspaper.readthedocs.io/en/latest/

    Takes a single url for `website_url`.

    Returns a `pd.DataFrame` with the following columns: 
        `headline`: the title of the article
        `publish_date`: the date the article was published
        `content`: the text body of the article
        `authors`: the authors of the article (in a list)
        `keywords`: any keywords that the newspaper NLP found. if none, is set to `np.nan`
        `summary`: the summary that the newspaper NLP created. if non, is set to `np.nan`
    
    """
    paper = newspaper.build(website_url)
    num_articles_found = len(paper.articles)
    #print("number found: ",num_articles_found)
    article_dict = {
        'headline': [],
        'publish_date': [],
        'content': [],
        'authors': [],
        'keywords': [],
        'summary': []
    }
    for i, paper_article in enumerate(paper.articles):
        print(f"{i+1}/{num_articles_found}", end="\r")
        try:
            article = Article(paper_article.url)
        except AttributeError as e:
            continue
        article.download()
        try:
            article.parse()
        except Exception as e:
            continue 
        article_dict['headline'].append(article.title)
        article_dict['publish_date'].append(article.publish_date)
        article_dict['content'].append(article.text)
        article_dict['authors'].append(article.authors)
        try:
            article.nlp()
            article_dict['keywords'].append(article.keywords)
            article_dict['summary'].append(article.summary)
        except Exception as e:
            article_dict['keywords'].append(np.nan)
            article_dict['summary'].append(np.nan)
        

    df = pd.DataFrame(article_dict)
    return df

def extract_names(news_urls):
    """
    Takes a list of news URL's as input. This function attempts to extract the hostname of the website by using the "www." and the ".com" of a URL.

    Returns a list of the extracted names.
    """
    news_names = []
    for url in news_urls:
        if "www." in url:
            website_name = url.split(".")[1]
        else:
            website_name = url.split(".com")[0].split("//")[-1]
        news_names.append(website_name)
    return news_names



def scrape_websites(news_names: list, news_urls: list, save_file: str ="data/news_data/news_data.pkl"):
    """
    This function scrapes a list of news websites for articles. 
    It then appends the data to the `save_file` data, deltes any duplicates, and saves the new DataFrame to the save file.

    Parameters:
    -----------
    `news_names`: list of the names as returned by `News_Scraper.extract_names`
    `news_urls`: list of news URL's
    `save_file`: string, '.pkl' file to store the resulting DataFrame.

    Returns:
    --------
    Nothing


    """

    frames = []

    for i, (name, url) in enumerate(zip(news_names, news_urls)):
        print()
        print(f"Scraping data for {name} ({i+1}/{len(news_names)})")
        news_df = scrape_news_website(url)
        news_df['source'] = name
        news_df['url'] = url
        news_df['date_pulled'] = datetime.date.today().strftime("%m-%d-%y")
        print(f"Found {news_df.shape[0]} usable articles.")
        frames.append(news_df)

    if os.path.exists(save_file):
        old_df = pd.read_pickle(save_file)
        print(f"Previous number of rows: {old_df.shape[0]:,}")
        frames.insert(0, old_df)

    df = pd.concat(frames)
    df.reset_index(inplace=True, drop=True)

    df = df[~df.duplicated(subset=['headline', 'publish_date', 'content'], keep='first')] #remove duplicates (leave first instance of duplicate)
    print(f"New number of rows {df.shape[0]:,}")
    df.to_pickle(save_file)

def main():
    from configs import NEWS_URLS, NEWS_SAVE_FILE
    news_names = extract_names(NEWS_URLS)
    lookup = {name: url for name, url in zip(news_names, NEWS_URLS)}
    scrape_websites(news_names, NEWS_URLS, save_file=NEWS_SAVE_FILE)

if __name__ == "__main__":
    main()