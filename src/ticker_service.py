from src.base.singleton import SingletonMeta
from src.base.alpaca_client import AlpacaClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetStatus
from alpaca.trading.models import Asset
from typing import Dict, Optional




class TickerService(metaclass=SingletonMeta):
    def __init__(self, alpaca_client: AlpacaClient = AlpacaClient()):
        self.alpaca_client = alpaca_client
        self.trading_client = self.alpaca_client.trading_client
        self.asset_dict: Optional[Dict[str, str]] = None
        self.asset_by_symbol: Optional[Dict[str, Asset]] = None

    def get_available_symbols(self, asset_class: str) -> list[str]:
        """
        Retrieve and store all available trading symbols for the asset class.
        
        Updates `self.asset_dict` with a mapping of symbols to asset names,
        and `self.asset_symbols` with a list of available symbols.

        'us_equity'
        'crypto'
        """
        assets = self._get_assets(asset_class=asset_class, active_only=False)
        self.asset_dict = {asset.symbol: asset.name for asset in assets}
        self.asset_by_symbol = {asset.symbol: asset for asset in assets}
        return list(self.asset_dict.keys())

    def get_active_symbols(self, asset_class: str) -> list[str]:
        """
        Retrieve and store active trading symbols for the asset class.

        Note: market data quotes may still exist for symbols that are not tradable.
        """
        assets = self._get_assets(asset_class=asset_class, active_only=True)
        self.asset_dict = {asset.symbol: asset.name for asset in assets}
        self.asset_by_symbol = {asset.symbol: asset for asset in assets}
        return list(self.asset_dict.keys())

    def _get_assets(self, asset_class: str, active_only: bool) -> list[Asset]:
        status = AssetStatus.ACTIVE if active_only else None
        search_params = GetAssetsRequest(asset_class=asset_class, status=status)
        return self.trading_client.get_all_assets(search_params)

    def lookup_stock_name(self, symbol: str) -> str:
        if self.asset_dict is None:
            self.get_active_symbols("us_equity")
        return self.asset_dict[symbol]
    
    def is_stock_symbol(self, symbol: str):
        available_symbols = self.get_available_symbols("us_equity")
        return symbol in available_symbols

    def is_tradable_stock_symbol(self, symbol: str) -> bool:
        """
        True only if the Alpaca asset is ACTIVE and marked tradable.
        """
        if not symbol:
            return False

        if self.asset_by_symbol is None:
            self.get_active_symbols("us_equity")

        asset = self.asset_by_symbol.get(symbol) if self.asset_by_symbol else None
        if asset is None:
            return False
        return bool(getattr(asset, "tradable", False))