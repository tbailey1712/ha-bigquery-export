#!/usr/bin/env python3
"""Simple test to validate the export logic."""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

async def test_simple_export():
    """Test a simple export without BigQuery."""
    print("🧪 TEST: Starting simple export test")
    
    # Mock Home Assistant components
    mock_hass = Mock()
    mock_hass.async_add_executor_job = AsyncMock()
    
    # Mock config
    config = {
        "project_id": "test-project",
        "dataset_id": "test-dataset",
        "table_id": "test-table",
        "service_account_key": '{"type": "service_account", "project_id": "test"}'
    }
    
    # Test time calculation
    end_time = datetime.utcnow()
    days_back = 1
    start_time = end_time - timedelta(days=days_back)
    
    print(f"🧪 TEST: Time range: {start_time} to {end_time}")
    
    # Mock the executor job to return 0 records
    mock_hass.async_add_executor_job.return_value = 0
    
    # Simple async function that mimics the export
    async def mock_export():
        print("🧪 TEST: Mock export starting")
        await asyncio.sleep(0.1)  # Simulate some work
        print("🧪 TEST: Mock export completed")
        return 0
    
    result = await mock_export()
    print(f"🧪 TEST: Result: {result}")
    
    return result

if __name__ == "__main__":
    result = asyncio.run(test_simple_export())
    print(f"🧪 TEST: Final result: {result}")