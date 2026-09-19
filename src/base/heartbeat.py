from src.base.singleton import SingletonMeta
from src.database.db_service import DatabaseService
from src.base.tl_logger import LoggingService

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
