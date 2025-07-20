#!/usr/bin/env python3
"""Test script to validate BigQuery export service."""

import asyncio
import logging
from datetime import datetime, timedelta
from unittest.mock import Mock

# Configure logging
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

def test_service_call():
    """Test the service call logic."""
    _LOGGER.warning("🧪 TEST: Starting service call test")
    
    # Mock call data
    call_data = {
        "days_back": 7
    }
    
    # Test parameter extraction
    days_back = call_data.get("days_back", 30)
    start_time = call_data.get("start_time")
    end_time = call_data.get("end_time")
    
    _LOGGER.warning("🧪 TEST: Parameters - days_back: %s, start_time: %s, end_time: %s", 
                   days_back, start_time, end_time)
    
    # Mock coordinator
    class MockCoordinator:
        async def async_manual_export(self, start_time=None, end_time=None, days_back=30):
            _LOGGER.warning("🧪 TEST: Mock coordinator called with start_time=%s, end_time=%s, days_back=%s", 
                           start_time, end_time, days_back)
            return True
    
    coordinator = MockCoordinator()
    
    # Test async call
    async def async_test():
        success = await coordinator.async_manual_export(
            start_time=start_time,
            end_time=end_time,
            days_back=days_back
        )
        _LOGGER.warning("🧪 TEST: Result: %s", success)
        return success
    
    # Run test
    result = asyncio.run(async_test())
    _LOGGER.warning("🧪 TEST: Final result: %s", result)
    
    return result

if __name__ == "__main__":
    test_service_call()