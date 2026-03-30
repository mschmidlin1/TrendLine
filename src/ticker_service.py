from src.base.singleton import SingletonMeta
from src.base.alpaca_client import AlpacaClient
from alpaca.trading.requests import GetAssetsRequest
from typing import Dict




class TickerService(metaclass=SingletonMeta):
    def __init__(self, alpaca_client: AlpacaClient = AlpacaClient()):
        self.alpaca_client = alpaca_client
        self.trading_client = self.alpaca_client.trading_client
        self.asset_dict = None

    def get_available_symbols(self, asset_class: str) -> list[str]:
        """
        Retrieve and store all available trading symbols for the asset class.
        
        Updates `self.asset_dict` with a mapping of symbols to asset names,
        and `self.asset_symbols` with a list of available symbols.

        'us_equity'
        'crypto'
        """
        search_params = GetAssetsRequest(asset_class=asset_class)
        assets = self.trading_client.get_all_assets(search_params)
        self.asset_dict = {asset.symbol: asset.name for asset in assets}
        return list(self.asset_dict.keys())

    def lookup_stock_name(self, symbol: str) -> str:
        if self.asset_dict is None:
            self.get_available_symbols("us_equity")
        return self.asset_dict[symbol]
    
    def is_stock_symbol(self, symbol: str):
        available_symbols = self.get_available_symbols("us_equity")
        return symbol in available_symbols