"""
Timer class for measuring elapsed time and managing time-based operations.
"""
import time
from typing import Optional, Callable
from datetime import datetime, timedelta


class Timer:
    """
    A versatile timer class for measuring elapsed time, creating countdowns,
    and managing time-based operations.
    
    Examples:
        # Basic usage - measure elapsed time
        timer = Timer()
        timer.start()
        # ... do some work ...
        elapsed = timer.elapsed()
        timer.stop()
        
        # Context manager usage
        with Timer() as t:
            # ... do some work ...
            pass
        print(f"Elapsed: {t.elapsed()}")
        
        # Countdown timer
        timer = Timer(duration=10.0)
        timer.start()
        while not timer.is_expired():
            print(f"Time remaining: {timer.remaining()}")
            time.sleep(1)
    """
    
    def __init__(self, duration: Optional[float] = None, auto_start: bool = False):
        """
        Initialize the timer.
        
        Args:
            duration: Optional duration in seconds for countdown functionality
            auto_start: If True, automatically start the timer on initialization
        """
        self._start_time: Optional[float] = None
        self._stop_time: Optional[float] = None
        self._pause_time: Optional[float] = None
        self._accumulated_time: float = 0.0
        self._duration: Optional[float] = duration
        self._is_running: bool = False
        self._is_paused: bool = False
        
        if auto_start:
            self.start()
    
    def start(self) -> 'Timer':
        """
        Start or restart the timer.
        
        Returns:
            Self for method chaining
        """
        if self._is_paused:
            # Resume from pause
            pause_duration = time.perf_counter() - self._pause_time
            self._start_time += pause_duration
            self._is_paused = False
        else:
            # Fresh start
            self._start_time = time.perf_counter()
            self._stop_time = None
            self._accumulated_time = 0.0
        
        self._is_running = True
        return self
    
    def stop(self) -> float:
        """
        Stop the timer and return elapsed time.
        
        Returns:
            Elapsed time in seconds
        """
        if not self._is_running:
            return self._accumulated_time
        
        if self._is_paused:
            self._accumulated_time = self._pause_time - self._start_time
        else:
            self._stop_time = time.perf_counter()
            self._accumulated_time = self._stop_time - self._start_time
        
        self._is_running = False
        self._is_paused = False
        return self._accumulated_time
    
    def pause(self) -> 'Timer':
        """
        Pause the timer without resetting it.
        
        Returns:
            Self for method chaining
        """
        if self._is_running and not self._is_paused:
            self._pause_time = time.perf_counter()
            self._is_paused = True
        return self
    
    def resume(self) -> 'Timer':
        """
        Resume the timer from a paused state.
        
        Returns:
            Self for method chaining
        """
        if self._is_paused:
            pause_duration = time.perf_counter() - self._pause_time
            self._start_time += pause_duration
            self._is_paused = False
        return self
    
    def reset(self) -> 'Timer':
        """
        Reset the timer to initial state.
        
        Returns:
            Self for method chaining
        """
        self._start_time = None
        self._stop_time = None
        self._pause_time = None
        self._accumulated_time = 0.0
        self._is_running = False
        self._is_paused = False
        return self
    
    def restart(self) -> 'Timer':
        """
        Reset and immediately start the timer.
        
        Returns:
            Self for method chaining
        """
        self.reset()
        return self.start()
    
    def elapsed(self) -> float:
        """
        Get the elapsed time in seconds.
        
        Returns:
            Elapsed time in seconds
        """
        if not self._is_running:
            return self._accumulated_time
        
        if self._is_paused:
            return self._pause_time - self._start_time
        
        return time.perf_counter() - self._start_time
    
    def elapsed_ms(self) -> float:
        """
        Get the elapsed time in milliseconds.
        
        Returns:
            Elapsed time in milliseconds
        """
        return self.elapsed() * 1000
    
    def elapsed_str(self, precision: int = 2) -> str:
        """
        Get a formatted string representation of elapsed time.
        
        Args:
            precision: Number of decimal places for seconds
            
        Returns:
            Formatted time string (e.g., "1h 23m 45.67s")
        """
        elapsed = self.elapsed()
        return self._format_time(elapsed, precision)
    
    def remaining(self) -> float:
        """
        Get the remaining time for countdown timers.
        
        Returns:
            Remaining time in seconds (0 if no duration set or expired)
        """
        if self._duration is None:
            return 0.0
        
        remaining = self._duration - self.elapsed()
        return max(0.0, remaining)
    
    def remaining_str(self, precision: int = 2) -> str:
        """
        Get a formatted string representation of remaining time.
        
        Args:
            precision: Number of decimal places for seconds
            
        Returns:
            Formatted time string
        """
        return self._format_time(self.remaining(), precision)
    
    def is_expired(self) -> bool:
        """
        Check if the countdown timer has expired.
        
        Returns:
            True if duration is set and elapsed time exceeds it
        """
        if self._duration is None:
            return False
        return self.elapsed() >= self._duration
    
    def is_running(self) -> bool:
        """
        Check if the timer is currently running.
        
        Returns:
            True if timer is running
        """
        return self._is_running and not self._is_paused
    
    def is_paused(self) -> bool:
        """
        Check if the timer is currently paused.
        
        Returns:
            True if timer is paused
        """
        return self._is_paused
    
    def set_duration(self, duration: float) -> 'Timer':
        """
        Set or update the countdown duration.
        
        Args:
            duration: Duration in seconds
            
        Returns:
            Self for method chaining
        """
        self._duration = duration
        return self
    
    @staticmethod
    def _format_time(seconds: float, precision: int = 2) -> str:
        """
        Format seconds into a human-readable string.
        
        Args:
            seconds: Time in seconds
            precision: Decimal places for seconds component
            
        Returns:
            Formatted string (e.g., "1h 23m 45.67s")
        """
        if seconds < 0:
            return "0s"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs:.{precision}f}s")
        
        return " ".join(parts)
    
    def __enter__(self) -> 'Timer':
        """Context manager entry - start the timer."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - stop the timer."""
        self.stop()
    
    def __str__(self) -> str:
        """String representation of the timer."""
        status = "running" if self.is_running() else "paused" if self.is_paused() else "stopped"
        elapsed = self.elapsed_str()
        
        if self._duration is not None:
            remaining = self.remaining_str()
            return f"Timer({status}, elapsed: {elapsed}, remaining: {remaining})"
        
        return f"Timer({status}, elapsed: {elapsed})"
    
    def __repr__(self) -> str:
        """Developer representation of the timer."""
        return (f"Timer(duration={self._duration}, is_running={self._is_running}, "
                f"is_paused={self._is_paused}, elapsed={self.elapsed():.3f}s)")


class StopWatch(Timer):
    """
    A stopwatch class that extends Timer with lap functionality.
    
    Example:
        stopwatch = StopWatch()
        stopwatch.start()
        # ... do some work ...
        lap1 = stopwatch.lap()
        # ... do more work ...
        lap2 = stopwatch.lap()
        stopwatch.stop()
        print(stopwatch.get_laps())
    """
    
    def __init__(self, auto_start: bool = False):
        """
        Initialize the stopwatch.
        
        Args:
            auto_start: If True, automatically start the stopwatch
        """
        super().__init__(auto_start=auto_start)
        self._laps: list[float] = []
        self._last_lap_time: float = 0.0
    
    def lap(self) -> float:
        """
        Record a lap time.
        
        Returns:
            Time since last lap (or start if first lap)
        """
        current_time = self.elapsed()
        lap_time = current_time - self._last_lap_time
        self._laps.append(lap_time)
        self._last_lap_time = current_time
        return lap_time
    
    def get_laps(self) -> list[float]:
        """
        Get all recorded lap times.
        
        Returns:
            List of lap times in seconds
        """
        return self._laps.copy()
    
    def get_laps_str(self, precision: int = 2) -> list[str]:
        """
        Get formatted lap times.
        
        Args:
            precision: Number of decimal places
            
        Returns:
            List of formatted lap time strings
        """
        return [self._format_time(lap, precision) for lap in self._laps]
    
    def reset(self) -> 'StopWatch':
        """
        Reset the stopwatch including lap times.
        
        Returns:
            Self for method chaining
        """
        super().reset()
        self._laps = []
        self._last_lap_time = 0.0
        return self
    
    def __str__(self) -> str:
        """String representation of the stopwatch."""
        base_str = super().__str__()
        if self._laps:
            return f"{base_str}, laps: {len(self._laps)}"
        return base_str


def time_function(func: Callable) -> Callable:
    """
    Decorator to time function execution.
    
    Example:
        @time_function
        def my_function():
            time.sleep(1)
        
        my_function()  # Prints: "my_function took 1.00s"
    """
    def wrapper(*args, **kwargs):
        timer = Timer()
        timer.start()
        result = func(*args, **kwargs)
        elapsed = timer.stop()
        print(f"{func.__name__} took {timer.elapsed_str()}")
        return result
    return wrapper
