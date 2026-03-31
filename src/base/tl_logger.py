import logging
import os
import sys

from filelock import FileLock

from src.configs import FILE_LOG_LEVEL, STDOUT_LOG_LEVEL, LOG_FILE, LOG_PATH
from src.base.singleton import SingletonMeta


class LockingFileHandler(logging.FileHandler):
    """
    FileHandler that acquires ``<logfile>.lock`` around each write so other processes
    can coordinate reads (e.g. tail) with the same lock path.
    """

    def __init__(self, filename, mode="a", encoding=None, delay=False, lock_path=None):
        super().__init__(filename, mode, encoding, delay)
        self._lock_path = lock_path or (str(filename) + ".lock")
        self._file_lock = FileLock(self._lock_path, timeout=60)

    def emit(self, record):
        self._file_lock.acquire()
        try:
            super().emit(record)
            self.flush()
        finally:
            self._file_lock.release()


class LoggingService(metaclass=SingletonMeta):
    """
    A singleton service class for centralized logging across an application.
    """

    def __init__(self):
        """
        Initializes the LoggingService with paths and log levels, sets up the directory and logger.
        """
        self.log_directory = LOG_PATH
        self.log_file = os.path.join(self.log_directory, LOG_FILE)
        self.file_log_level = FILE_LOG_LEVEL
        self.stdout_log_level = STDOUT_LOG_LEVEL
        self.logger = logging.getLogger(__name__)
        self.setup_logging_directory()
        self.setup_logger()

    def setup_logging_directory(self):
        """
        Ensures that the log directory exists and creates the log file if it does not exist.
        """
        if not os.path.isdir(self.log_directory):
            os.mkdir(self.log_directory)
        if not os.path.isfile(self.log_file):
            with open(self.log_file, "w") as file:
                pass

    def setup_logger(self):
        """
        Configures the logger with file and console handlers using the specified log levels and format.
        """
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.DEBUG)

        console = logging.StreamHandler(sys.stdout)
        console.setLevel(getattr(logging, self.stdout_log_level))
        console.setFormatter(formatter)

        file_handler = LockingFileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(getattr(logging, self.file_log_level))
        file_handler.setFormatter(formatter)

        root.addHandler(console)
        root.addHandler(file_handler)

        # filelock logs at DEBUG while acquiring the lock; routing that through this handler recurses.
        logging.getLogger("filelock").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        logging.getLogger("urllib3.connection").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("watchdog").setLevel(logging.WARNING)
    def log_debug(self, message: str, **kwargs):
        """
        Logs a debug message.
        Args:
            message (str): The message to log.
            **kwargs: Additional keyword arguments to pass to the logger.
        """
        self.logger.debug(message, **kwargs)

    def log_info(self, message: str, **kwargs):
        """
        Logs an informational message.
        Args:
            message (str): The message to log.
            **kwargs: Additional keyword arguments to pass to the logger.
        """
        self.logger.info(message, **kwargs)

    def log_warning(self, message: str, **kwargs):
        """
        Logs a warning message.
        Args:
            message (str): The message to log.
            **kwargs: Additional keyword arguments to pass to the logger.
        """
        self.logger.warning(message, **kwargs)

    def log_error(self, message: str, **kwargs):
        """
        Logs an error message.
        Args:
            message (str): The message to log.
            **kwargs: Additional keyword arguments to pass to the logger.
        """
        self.logger.error(message, **kwargs)
