from singleton import SingletonMeta
from tl_logger import LoggingService
import datetime
import pytz

class TimingService(metaclass=SingletonMeta):
    def __init__(self):
        self.logging_service = LoggingService()
    







class Market_Monitor():
    """Market Monitor can tell you if the market is open or not. It also has functionality for sleeping until the next market open."""
    def __init__(self, trading_client, TIMEZONE):
        self.TIMEZONE = TIMEZONE
        self.trading_client = trading_client
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

    def market_closed_loop(self, continuous=False, num_seconds=5):
        """
        The market closed loop will run until the market is open again. It will not hand the thread back to the main program until the market is open.

        
        """
        logging.info(f"Next market open is: {self.next_open}")
        logging.info(f"Sleeping for {self.time_until_open}.")
        time.sleep(self.time_until_open.total_seconds())
        logging.info(f"Waking up! Will now continually check until market is open.")
        if continuous:
            self.check_open_continuous()
        else:
            self.check_open_seconds(num_seconds)
    
    def check_open_seconds(self, num_seconds):
        while True:
            self.update()
            if self.market_open:
                break
            logging.debug(f"Market not open. Sleeping for {num_seconds} seconds.") 
            time.sleep(num_seconds)

    def check_open_continuous(self):
        while True:
            self.update()
            if self.market_open:
                break
            logging.debug(f"Market not open.")




if __name__ == "__main__":
    trading_client = TradingClient(PAPER_API_ID, PAPER_SECRET_KEY, paper=True)
    monitor = Market_Monitor(trading_client, TIMEZONE)
    print("Current Time:", monitor.tod)
    if not monitor.is_market_open():
        monitor.market_closed_loop()
    print("Returning to main.")