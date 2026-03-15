import logging
import logging.config
from configs import FILE_LOG_LEVEL, STDOUT_LOG_LEVEL, LOG_FILE, LOG_PATH
from singleton import SingletonMeta
import os

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
            with open(self.log_file, 'w') as file:
                pass

    def setup_logger(self):
        """
        Configures the logger with file and console handlers using the specified log levels and format.
        """
        logging_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s - %(levelname)s - %(message)s'
                },
            },
            'handlers': {
                'file': {
                    'level': self.file_log_level,
                    'class': 'logging.FileHandler',
                    'filename': self.log_file,
                    'formatter': 'standard',
                },
                'console': {
                    'level': self.stdout_log_level,
                    'class': 'logging.StreamHandler',
                    'formatter': 'standard',
                    'stream': 'ext://sys.stdout',
                },
            },
            'loggers': {
                '': {
                    'handlers': ['file', 'console'],
                    'level': 'DEBUG',
                    'propagate': True
                },
            }
        }
        logging.config.dictConfig(logging_config)

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
