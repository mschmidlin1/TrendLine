



from singleton import SingletonMeta


class SentimentService(metaclass=SingletonMeta):
    """
    A class for determining sentiment of financial news data.
    Positive sentiment indicates an indication to buy a stock, 
    negative sentiment indicates an indication to sell a stock.
    """
    def __init__(self):
        pass