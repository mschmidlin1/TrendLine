import unittest
import time
from datetime import timedelta, datetime
from src.timing_service import TimingService


class TestTimingService(unittest.TestCase):
    """Unit tests for TimingService class."""

    def setUp(self):
        """Reset the singleton instance before each test."""
        # Clear the singleton instance to ensure clean state for each test
        if TimingService in TimingService._instances:
            del TimingService._instances[TimingService]

    def test_singleton_pattern(self):
        """Test that TimingService follows the singleton pattern."""
        service1 = TimingService(scrape_frequency=timedelta(seconds=2))
        service2 = TimingService(scrape_frequency=timedelta(seconds=5))
        
        # Both should be the same instance
        self.assertIs(service1, service2)
        
        # Modify state in one instance
        service1.mark_scrape_completed()
        
        # Verify the change is reflected in the other instance
        self.assertIsNotNone(service2.get_last_scrape_time())
        self.assertEqual(service1.get_last_scrape_time(), service2.get_last_scrape_time())

    def test_initial_state(self):
        """Test that the service initializes with correct default values."""
        service = TimingService(scrape_frequency=timedelta(seconds=2))
        service.reset()
        
        # Check initial state
        self.assertIsNone(service.get_last_scrape_time())
        self.assertEqual(service.get_scrape_frequency(), timedelta(seconds=2))
        self.assertTrue(service.is_time_to_scrape())

    def test_first_scrape_ready_immediately(self):
        """Test that the first scrape can happen immediately."""
        service = TimingService(scrape_frequency=timedelta(seconds=2))
        service.reset()
        
        # Should be ready to scrape immediately
        self.assertTrue(service.is_time_to_scrape())
        self.assertEqual(service.time_until_next_scrape(), 0.0)

    def test_mark_scrape_completed(self):
        """Test that marking a scrape as completed updates internal state."""
        service = TimingService(scrape_frequency=timedelta(seconds=2))
        service.reset()
        
        # Record time before marking completion
        before_time = datetime.now()
        
        # Mark scrape as completed
        service.mark_scrape_completed()
        
        # Record time after marking completion
        after_time = datetime.now()
        
        # Check that last scrape time is set and within expected range
        last_scrape = service.get_last_scrape_time()
        self.assertIsNotNone(last_scrape)
        self.assertGreaterEqual(last_scrape, before_time)
        self.assertLessEqual(last_scrape, after_time)
        
        # Check that next scrape time is set
        next_scrape = service.get_next_scrape_time()
        self.assertIsNotNone(next_scrape)
        
        # Verify next scrape time = last scrape time + frequency
        expected_next = last_scrape + timedelta(seconds=2)
        self.assertEqual(next_scrape, expected_next)

    def test_is_time_to_scrape_after_completion(self):
        """Test that after marking scrape complete, service correctly reports not ready."""
        service = TimingService(scrape_frequency=timedelta(seconds=2))
        service.reset()
        
        # Mark scrape as completed
        service.mark_scrape_completed()
        
        # Should not be ready immediately after completion
        self.assertFalse(service.is_time_to_scrape())
        
        # Wait for the frequency period to pass
        time.sleep(2.1)
        
        # Should now be ready to scrape again
        self.assertTrue(service.is_time_to_scrape())

    def test_time_until_next_scrape_countdown(self):
        """Test that time_until_next_scrape returns accurate countdown."""
        service = TimingService(scrape_frequency=timedelta(seconds=3))
        service.reset()
        
        # Mark scrape as completed
        service.mark_scrape_completed()
        
        # Should be approximately 3 seconds until next scrape
        time_remaining = service.time_until_next_scrape()
        self.assertAlmostEqual(time_remaining, 3.0, delta=0.1)
        
        # Wait 1 second
        time.sleep(1.0)
        
        # Should be approximately 2 seconds remaining
        time_remaining = service.time_until_next_scrape()
        self.assertAlmostEqual(time_remaining, 2.0, delta=0.2)
        
        # Wait 2.5 more seconds (total 3.5 seconds)
        time.sleep(2.5)
        
        # Should be 0.0 (past due)
        time_remaining = service.time_until_next_scrape()
        self.assertEqual(time_remaining, 0.0)

    def test_multiple_scrape_cycles(self):
        """Test that the service handles multiple scrape cycles correctly."""
        service = TimingService(scrape_frequency=timedelta(seconds=1))
        service.reset()
        
        # Run 3 scrape cycles
        for i in range(3):
            # Should be ready to scrape
            self.assertTrue(service.is_time_to_scrape(), f"Cycle {i+1}: Should be ready to scrape")
            
            # Mark scrape as completed
            service.mark_scrape_completed()
            
            # Should not be ready immediately after
            self.assertFalse(service.is_time_to_scrape(), f"Cycle {i+1}: Should not be ready immediately")
            
            # Wait for next cycle
            time.sleep(1.1)

    def test_reset_functionality(self):
        """Test that reset() properly clears state."""
        service = TimingService(scrape_frequency=timedelta(seconds=1))
        service.reset()
        
        # Mark scrape as completed multiple times
        service.mark_scrape_completed()
        time.sleep(1.1)
        service.mark_scrape_completed()
        
        # Verify state is populated
        self.assertIsNotNone(service.get_last_scrape_time())
        self.assertIsNotNone(service.get_next_scrape_time())
        
        # Reset the service
        service.reset()
        
        # Verify state is cleared
        self.assertIsNone(service.get_last_scrape_time())
        self.assertIsNone(service.get_next_scrape_time())
        self.assertTrue(service.is_time_to_scrape())
        
        # Verify frequency is preserved
        self.assertEqual(service.get_scrape_frequency(), timedelta(seconds=1))

    def test_custom_frequency_in_constructor(self):
        """Test that custom frequency can be set via constructor."""
        service = TimingService(scrape_frequency=timedelta(seconds=5))
        service.reset()
        
        # Verify frequency is set correctly
        self.assertEqual(service.get_scrape_frequency(), timedelta(seconds=5))
        
        # Mark scrape as completed
        service.mark_scrape_completed()
        
        # Verify next scrape time uses the 5-second frequency
        last_scrape = service.get_last_scrape_time()
        next_scrape = service.get_next_scrape_time()
        expected_next = last_scrape + timedelta(seconds=5)
        self.assertEqual(next_scrape, expected_next)
        
        # Verify time until next scrape is approximately 5 seconds
        time_remaining = service.time_until_next_scrape()
        self.assertAlmostEqual(time_remaining, 5.0, delta=0.1)

    def test_get_methods(self):
        """Test that all getter methods return correct values."""
        service = TimingService(scrape_frequency=timedelta(seconds=2))
        service.reset()
        
        # Before any scrapes
        self.assertIsNone(service.get_last_scrape_time())
        self.assertIsNone(service.get_next_scrape_time())
        self.assertEqual(service.get_scrape_frequency(), timedelta(seconds=2))
        
        # After marking scrape completed
        service.mark_scrape_completed()
        
        # Verify getters return datetime objects
        self.assertIsInstance(service.get_last_scrape_time(), datetime)
        self.assertIsInstance(service.get_next_scrape_time(), datetime)
        self.assertEqual(service.get_scrape_frequency(), timedelta(seconds=2))

    def test_edge_case_zero_frequency(self):
        """Test behavior with zero frequency."""
        service = TimingService(scrape_frequency=timedelta(seconds=0))
        service.reset()
        
        # Mark scrape as completed
        service.mark_scrape_completed()
        
        # With zero frequency, should always be ready to scrape
        self.assertTrue(service.is_time_to_scrape())
        self.assertEqual(service.time_until_next_scrape(), 0.0)

    def test_concurrent_access_singleton(self):
        """Test singleton behavior with state changes."""
        service1 = TimingService(scrape_frequency=timedelta(seconds=2))
        service1.reset()
        
        # Mark scrape as completed via service1
        service1.mark_scrape_completed()
        
        # Get another reference to the singleton
        service2 = TimingService()
        
        # Verify service2 reflects the change made via service1
        self.assertIsNotNone(service2.get_last_scrape_time())
        self.assertEqual(service1.get_last_scrape_time(), service2.get_last_scrape_time())
        
        # Verify they are the same instance
        self.assertIs(service1, service2)

    def test_set_scrape_frequency(self):
        """Test that set_scrape_frequency updates the frequency and recalculates next scrape time."""
        service = TimingService(scrape_frequency=timedelta(seconds=2))
        service.reset()
        
        # Mark scrape as completed with initial frequency
        service.mark_scrape_completed()
        initial_next_scrape = service.get_next_scrape_time()
        
        # Change frequency
        service.set_scrape_frequency(timedelta(seconds=5))
        
        # Verify frequency is updated
        self.assertEqual(service.get_scrape_frequency(), timedelta(seconds=5))
        
        # Verify next scrape time is recalculated
        new_next_scrape = service.get_next_scrape_time()
        self.assertNotEqual(initial_next_scrape, new_next_scrape)
        
        # Verify new next scrape time uses new frequency
        expected_next = service.get_last_scrape_time() + timedelta(seconds=5)
        self.assertEqual(new_next_scrape, expected_next)

    def test_time_until_next_scrape_before_first_scrape(self):
        """Test that time_until_next_scrape returns 0.0 before first scrape."""
        service = TimingService(scrape_frequency=timedelta(seconds=2))
        service.reset()
        
        # Before any scrapes, should return 0.0
        self.assertEqual(service.time_until_next_scrape(), 0.0)

    def test_get_next_scrape_time_lazy_calculation(self):
        """Test that get_next_scrape_time calculates the value if not already set."""
        service = TimingService(scrape_frequency=timedelta(seconds=2))
        service.reset()
        
        # Mark scrape as completed
        service.mark_scrape_completed()
        
        # Manually clear next scrape time to test lazy calculation
        service._next_scrape_time = None
        
        # get_next_scrape_time should calculate it
        next_scrape = service.get_next_scrape_time()
        self.assertIsNotNone(next_scrape)
        
        # Verify it's calculated correctly
        expected_next = service.get_last_scrape_time() + timedelta(seconds=2)
        self.assertEqual(next_scrape, expected_next)


if __name__ == '__main__':
    unittest.main()
