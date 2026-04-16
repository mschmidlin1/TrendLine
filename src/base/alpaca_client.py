from src.base.singleton import SingletonMeta
from alpaca.trading.client import TradingClient
from src.configs import ALPACA_CHOSEN_API_ID, ALPACA_CHOSEN_SECRET_KEY, USE_PAPER
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry




class AlpacaClient(metaclass=SingletonMeta):
    def __init__(self, api_id=ALPACA_CHOSEN_API_ID, secret_key=ALPACA_CHOSEN_SECRET_KEY, paper=USE_PAPER):
        self.api_id = ALPACA_CHOSEN_API_ID
        self.secret_key = ALPACA_CHOSEN_SECRET_KEY
        self.paper = paper
        
        self.trading_client: TradingClient = TradingClient(api_id, secret_key, paper=paper)

        # Alpaca SDK retries only on certain HTTP status codes (e.g. 429/504) and does not
        # retry transport-level failures like `RemoteDisconnected`. Mount a retrying adapter
        # on the shared session to make those transient failures non-fatal.
        retry = Retry(
            total=5,
            connect=5,
            read=5,
            status=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.trading_client._session.mount("https://", adapter)
        self.trading_client._session.mount("http://", adapter)