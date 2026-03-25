from src.base.singleton import SingletonMeta
from src.base.alpaca_client import AlpacaClient
from alpaca.trading.requests import GetAssetsRequest





class TickerService(metaclass=SingletonMeta):
    def __init__(self, alpaca_client: AlpacaClient = AlpacaClient()):
        self.alpaca_client = alpaca_client
        self.trading_client = self.alpaca_client.trading_client

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
    
    def is_stock_symbol(self, symbol: str):
        available_symbols = self.get_available_symbols("us_equity")
        return symbol in available_symbols