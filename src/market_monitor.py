from src.base.singleton import SingletonMeta
from src.base.tl_logger import LoggingService
from src.base.alpaca_client import AlpacaClient
import datetime
import pytz
    

class MarketMonitorService(metaclass=SingletonMeta):
    """Market Monitor can tell you if the market is open or not. """
    def __init__(self, alpaca_client: AlpacaClient = AlpacaClient(), TIMEZONE="US/Eastern"):
        self.TIMEZONE = TIMEZONE
        self.alpaca_client: AlpacaClient = alpaca_client
        self.trading_client = self.alpaca_client.trading_client
        self._logger = LoggingService()
        self.tzinfo = pytz.timezone(self.TIMEZONE)
        self.update()

    def current_dt(self):
        self.dt = datetime.datetime.now(self.tzinfo)

    def current_tod(self):
        self.current_dt()
        self.tod = self.dt.time()

    def get_trade_clock(self):
        self.trade_clock = self.trading_client.get_clock()

    def get_trade_calendar(self):
        self.trade_calendars = self.trading_client.get_calendar()
        self.calendar_dict = {
            'date': [],
            'open': [],
            'close': []
        }

        for calendar in self.trade_calendars:
            self.calendar_dict['date'].append(calendar.date)
            self.calendar_dict['close'].append(calendar.close)
            self.calendar_dict['open'].append(calendar.open)

    def trading_date(self, date: datetime.date):
        """Check is the passed `date` is in the list of known trading dates.
        
        The trading dates covered are from 1970-2029."""
        return date in self.calendar_dict['date']

    def update(self):
        self.current_tod()
        self.get_trade_clock()
        self.get_trade_calendar()
        self.market_open = self.trade_clock.is_open
        self.next_open = self.trade_clock.next_open
        self.next_close = self.trade_clock.next_close
        self.time_until_open = datetime.timedelta(minutes=0)
        if not self.market_open:
            self.time_until_open = self.next_open - self.dt

    def is_market_open(self):
        self.update()
        return self.market_open

    
    





if __name__ == "__main__":
    pass