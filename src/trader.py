from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import GetAssetsRequest
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest, CryptoLatestQuoteRequest
from alpaca.data.requests import CryptoBarsRequest
from alpaca.trading.models import Order
from alpaca.data.timeframe import TimeFrame
from configs import ALPACA_CHOSEN_SECRET_KEY
from tl_logger import LoggingService
import pandas as pd

class Trader():
    timeframe_lookup = {
        'day': TimeFrame.Day,
        'hour': TimeFrame.Hour,
        'minute': TimeFrame.Minute
    }
    def __init__(self, API_ID, SECRET_KEY, paper=True):
        self.API_ID = API_ID
        self.SECRET_KEY = SECRET_KEY
        self.trading_client = TradingClient(API_ID, SECRET_KEY, paper=paper)

        #logging.debug("Instance of Trader() class created.")

    def get_account(self):
        self.account = self.trading_client.get_account()
    
    def get_buying_power(self):
        self.get_account()
        self.buying_power = float(self.account.buying_power)

    def get_available_symbols(self):
        search_params = GetAssetsRequest(asset_class=self.asset_class)
        assets = self.trading_client.get_all_assets(search_params)
        self.asset_dict = {asset.symbol: asset.name for asset in assets}
        self.asset_symbols = list(self.asset_dict.keys())
    
    def get_ask_price(self, symbol):
        quote = self.get_quote(symbol)
        return quote.ask_price

    def get_bid_price(self, symbol):
        quote = self.get_quote(symbol)
        return quote.bid_price
    
    def get_all_positions(self, ):
        """
        Gets all positions (cryto and stock) and stores them in a
        `pd.DataFrame` which can be accessed at `self.positions_df`. """
        self.get_account()
        all_positions = self.trading_client.get_all_positions()
        columns = list(all_positions[0].dict().keys())
        positions_dict = {key: [] for key in columns}

        for position in all_positions:
            for key in columns:
                positions_dict[key].append(position.dict()[key])
        
        self.positions_df = pd.DataFrame(positions_dict)
        for col in self.positions_df.columns:
            self.positions_df[col] = pd.to_numeric(self.positions_df[col], errors='ignore')

    def get_all_orders(self):
        """
        Gets all orders (crypto and stock) and stores them in a 
        `pd.DataFrame` which can be accessed at `self.orders_df`.
        
        A return of `0` means that `self.orders_df` has been successfully stored. 
        A return of `1` means that `self.orders_df` has been set to `None` becuase there were no open orders (empty dataframe). """
        self.get_account()
        all_orders = self.trading_client.get_orders()
        if len(all_orders)==0:
            self.orders_df = None
            return 1
        columns = list(all_orders[0].dict().keys())
        orders_dict = {key: [] for key in columns}

        for order in all_orders:
            for key in columns:
                orders_dict[key].append(order.dict()[key])
        
        self.orders_df = pd.DataFrame(orders_dict)
        for col in self.orders_df.columns:
            self.orders_df[col] = pd.to_numeric(self.orders_df[col], errors='ignore')
        return 0

    def buy(self, symbol: str, quantity=None, price=None, side=OrderSide.BUY, time_in_force=TimeInForce.GTC):
        """Must choose either to *buy* a `quantity` or buy a specific amount in terms of
        `price`. Both should be float or int arguments."""
        #makes sure the symbol is legitimate
        if symbol not in self.asset_symbols:
            raise ValueError(f"symbol {symbol} not available.")
        #check function imputs
        if (quantity is None and price is None) or (quantity!=None and price!=None):
            raise ValueError("Must specify either quantity or price.")
        #check to make sure you have enough buying power
        if price==None:
            price = self.get_ask_price(symbol)*quantity
        self.get_buying_power()
        if price>self.buying_power:
            logging.warning("Not enough funds to buy {price} of '{symbol}'. Buying power is {self.buying_power}")
            return 1
        elif quantity is None:
            logging.info(f"Buying {price} dollars of {symbol}.")
            market_order_data = MarketOrderRequest(
                                symbol=symbol,
                                notional=price,
                                side=side,
                                time_in_force=time_in_force
                            )
        else:
            logging.info(f"Buying {quantity} shares of {symbol}.")
            market_order_data = MarketOrderRequest(
                                symbol=symbol,
                                qty=quantity,
                                side=side,
                                time_in_force=time_in_force
                            )
        market_order = self.trading_client.submit_order(market_order_data)
        self.get_buying_power()
        return 0

    def sell_all(self, cancel_orders=True):
        self.trading_client.close_all_positions(cancel_orders=cancel_orders)

    def sell(self, symbol: str, quantity=None, price=None, side=OrderSide.SELL, time_in_force=TimeInForce.GTC):
        """Must choose either to *sell* a `quantity` or buy a specific amount in terms of
        `price`. Both should be float or int arguments."""
        #makes sure the symbol is legitimate
        if symbol not in self.asset_symbols:
            raise ValueError(f"symbol {symbol} not available.")
        #check function imputs
        if (quantity is None and price is None) or (quantity!=None and price!=None):
            raise ValueError("Must specify either quantity or price.")
        
        if quantity is None:
            logging.info(f"Selling {price} dollars of {symbol}.")
            market_order_data = MarketOrderRequest(
                                symbol=symbol,
                                notional=price,
                                side=side,
                                time_in_force=time_in_force
                            )
        else:
            logging.info(f"Selling {quantity} shares of {symbol}.")
            market_order_data = MarketOrderRequest(
                                symbol=symbol,
                                qty=quantity,
                                side=side,
                                time_in_force=time_in_force
                            )
        market_order = self.trading_client.submit_order(market_order_data)
        self.get_buying_power()
        return 0

    def cancel_all_orders(self):
        cancel_statuses = self.trading_client.cancel_orders()
        return cancel_statuses

class Stock_Trader(Trader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logging.debug("Instace of Stock_Trader() class created.")
        self.asset_class = 'us_equity'
        self.get_available_symbols()

    def get_quote(self, symbol):
        client = StockHistoricalDataClient(self.API_ID, self.SECRET_KEY)
        multisymbol_request_params = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        return client.get_stock_latest_quote(multisymbol_request_params)[symbol]

    def get_bars(self, symbol: str, start: datetime, end: datetime, time_resolution='day'):

        client = StockHistoricalDataClient(self.API_ID, self.SECRET_KEY)
        request_params = StockBarsRequest(
                        symbol_or_symbols=symbol,
                        timeframe=self.timeframe_lookup[time_resolution],
                        start=start,
                        end=end
                 )

        bars = client.get_stock_bars(request_params)
        return bars.df

class Crypto_Trader(Trader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logging.debug("Instace of Crypto_Trader() class created.")
        self.asset_class = 'crypto'
        self.get_available_symbols()

    def get_quote(self, symbol):
        client = CryptoHistoricalDataClient(self.API_ID, self.SECRET_KEY)
        multisymbol_request_params = CryptoLatestQuoteRequest(symbol_or_symbols=symbol)
        return client.get_crypto_latest_quote(multisymbol_request_params)[symbol]

    def get_bars(self, symbol: str, start: datetime, end: datetime, time_resolution='day'):
        client = CryptoHistoricalDataClient()
        request_params = CryptoBarsRequest(
                        symbol_or_symbols=symbol,
                        timeframe=self.timeframe_lookup[time_resolution],
                        start=start,
                        end=end
                 )
        bars = client.get_crypto_bars(request_params)
        return bars.df


if __name__ == "__main__":
    pass