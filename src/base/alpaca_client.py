from src.base.singleton import SingletonMeta
from alpaca.trading.client import TradingClient
from src.configs import ALPACA_CHOSEN_API_ID, ALPACA_CHOSEN_SECRET_KEY, USE_PAPER




class AlpacaClient(metaclass=SingletonMeta):
    def __init__(self, api_id=ALPACA_CHOSEN_API_ID, secret_key=ALPACA_CHOSEN_SECRET_KEY, paper=USE_PAPER):
        self.api_id = ALPACA_CHOSEN_API_ID
        self.secret_key = ALPACA_CHOSEN_SECRET_KEY
        self.paper = paper
        
        self.trading_client: TradingClient = TradingClient(api_id, secret_key, paper=paper)