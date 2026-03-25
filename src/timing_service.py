"""
TimingService - Manages timing logic for scraping and trading iterations.

This service determines when to perform scraping operations based on configurable
time intervals. It follows the Singleton pattern to ensure consistent timing
across the application.
"""

from src.base.singleton import SingletonMeta
from src.configs import SCRAPE_FREQUENCY
from datetime import datetime, timedelta
from typing import Optional


class TimingService(metaclass=SingletonMeta):
    """
    Singleton service for managing scraping timing logic.
    
    This service tracks when scrapes occur and determines when the next scrape
    should happen based on a configurable frequency interval.
    
    Attributes:
        _last_scrape_time: Timestamp of the last completed scrape operation.
        _scrape_frequency: Time interval between scrapes.
        _next_scrape_time: Calculated timestamp for the next scheduled scrape.
    
    Example:
        # Use default frequency from configs
        timing_service = TimingService()
        
        if timing_service.is_time_to_scrape():
            # Perform scraping operations
            timing_service.mark_scrape_completed()
        
        # Sleep until next scrape
        wait_time = timing_service.time_until_next_scrape()
        time.sleep(wait_time)
    """
    
    def __init__(self, scrape_frequency: timedelta = SCRAPE_FREQUENCY):
        """
        Initialize the TimingService with configurable scrape frequency.
        
        Args:
            scrape_frequency: Time interval between scrapes. Defaults to 
                            SCRAPE_FREQUENCY from configs.
        """
        self._last_scrape_time: Optional[datetime] = None
        self._scrape_frequency: timedelta = scrape_frequency
        self._next_scrape_time: Optional[datetime] = None
    
    def is_time_to_scrape(self) -> bool:
        """
        Check if it's time to perform another scrape operation.
        
        This is the main method users will call to determine if scraping
        should occur. Returns True on first call (no scrapes yet) or when
        the scheduled next scrape time has been reached.
        
        Returns:
            bool: True if it's time to scrape, False otherwise.
        """
        # First scrape should happen immediately
        if self._last_scrape_time is None:
            return True
        
        # Calculate next scrape time if not already set
        if self._next_scrape_time is None:
            self._next_scrape_time = self._last_scrape_time + self._scrape_frequency
        
        # Check if current time has reached or passed the next scrape time
        return datetime.now() >= self._next_scrape_time
    
    def mark_scrape_completed(self) -> None:
        """
        Record that a scrape operation has been completed.
        
        Updates the last scrape time to now and calculates the next
        scheduled scrape time. This method should be called after
        successfully completing a scrape operation.
        """
        self._last_scrape_time = datetime.now()
        self._next_scrape_time = self._last_scrape_time + self._scrape_frequency
    
    def time_until_next_scrape(self) -> float:
        """
        Calculate how many seconds remain until the next scrape should occur.
        
        Returns:
            float: Seconds until next scrape. Returns 0.0 if ready to scrape
                  immediately (either no scrapes yet or past due).
        """
        # Ready to scrape immediately if no scrapes have occurred
        if self._last_scrape_time is None:
            return 0.0
        
        # Calculate next scrape time if not already set
        if self._next_scrape_time is None:
            self._next_scrape_time = self._last_scrape_time + self._scrape_frequency
        
        # Calculate time difference
        time_diff = self._next_scrape_time - datetime.now()
        
        # Return 0.0 if we're past due, otherwise return seconds remaining
        return max(0.0, time_diff.total_seconds())
    
    def get_last_scrape_time(self) -> Optional[datetime]:
        """
        Retrieve the timestamp of the last completed scrape.
        
        Returns:
            Optional[datetime]: Timestamp of last scrape, or None if no
                              scrape has occurred yet.
        """
        return self._last_scrape_time
    
    def get_next_scrape_time(self) -> Optional[datetime]:
        """
        Retrieve the scheduled timestamp for the next scrape.
        
        Returns:
            Optional[datetime]: Timestamp of next scheduled scrape, or None
                              if no scrape has been completed yet.
        """
        # Calculate next scrape time if we have a last scrape time but no next time
        if self._next_scrape_time is None and self._last_scrape_time is not None:
            self._next_scrape_time = self._last_scrape_time + self._scrape_frequency
        
        return self._next_scrape_time
    
    def get_scrape_frequency(self) -> timedelta:
        """
        Get the configured scrape frequency interval.
        
        Returns:
            timedelta: The time interval between scrapes.
        """
        return self._scrape_frequency
    
    def reset(self) -> None:
        """
        Reset the timing service to initial state.
        
        Clears all timing state (last scrape time and next scrape time)
        but preserves the scrape frequency configuration. Useful for
        testing or restarting the timing cycle.
        """
        self._last_scrape_time = None
        self._next_scrape_time = None
    
    def set_scrape_frequency(self, frequency: timedelta) -> None:
        """
        Override the scrape frequency dynamically.
        
        Updates the scrape frequency and recalculates the next scrape time
        if a scrape has already been completed. For testing, prefer passing
        scrape_frequency to the constructor instead.
        
        Args:
            frequency: New time interval between scrapes.
        """
        self._scrape_frequency = frequency
        
        # Recalculate next scrape time if we have a last scrape time
        if self._last_scrape_time is not None:
            self._next_scrape_time = self._last_scrape_time + self._scrape_frequency
