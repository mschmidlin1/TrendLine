from trend_core.base.singleton import SingletonMeta
from trend_core.database.db_service import DatabaseService
from trend_core.base.tl_logger import LoggingService

class HeartbeatService(metaclass=SingletonMeta):
    def __init__(self):
        self._db_service = DatabaseService()
        self._logger = LoggingService()

    def pulse(self):
        """
        Update pulse in DB.
        """
        self._db_service.execute(
            """
            UPDATE heartbeat
            SET last_seen = now()
            WHERE id = 1
            """
        )
