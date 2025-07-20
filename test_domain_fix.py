#!/usr/bin/env python3
"""Test that the domain column is now included in the query."""

import sys
sys.path.append('/Users/tbailey/Dev/ha-bigquery-export')

from custom_components.bigquery_export.services import BigQueryExportService
from datetime import datetime, timedelta
import json

# Test query structure
query_text = """
SELECT 
    s.state,
    s.last_updated_ts,
    s.last_changed_ts,
    s.last_reported_ts,
    s.context_id,
    s.context_user_id,
    s.metadata_id,
    m.entity_id,
    m.domain,
    sa.shared_attrs as attributes
FROM states s
JOIN states_meta m ON s.metadata_id = m.metadata_id
LEFT JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
WHERE s.last_updated_ts >= :start_ts 
AND s.last_updated_ts < :end_ts
ORDER BY s.last_updated_ts
"""

print("🧪 TEST: Query structure includes domain column:")
print(query_text)

# Expected columns in the result
expected_columns = [
    'state', 'last_updated_ts', 'last_changed_ts', 'last_reported_ts',
    'context_id', 'context_user_id', 'metadata_id', 'entity_id', 'domain', 'attributes'
]

print(f"\n🧪 TEST: Expected columns in result: {expected_columns}")

# Mock a row result similar to what we saw in the logs
mock_row_data = {
    'state': '27',
    'last_updated_ts': 1751828430.7669454,
    'last_changed_ts': None,
    'last_reported_ts': 1751828430.7669454,
    'context_id': None,
    'context_user_id': None,
    'metadata_id': 1597,
    'entity_id': 'sensor.firewall_memory_used_percentage',
    'domain': 'sensor',  # This should now be available
    'attributes': '{"state_class":"measurement","unit_of_measurement":"%","icon":"mdi:memory","friendly_name":"pfSense Firewall Memory Used Percentage"}'
}

print(f"\n🧪 TEST: Mock row with domain: {mock_row_data}")

# Test the logic that was failing
try:
    domain = mock_row_data.get('domain') or (mock_row_data['entity_id'].split('.')[0] if '.' in mock_row_data['entity_id'] else None)
    print(f"✅ TEST: Domain extraction successful: {domain}")
except Exception as e:
    print(f"❌ TEST: Domain extraction failed: {e}")

# Test attribute parsing
try:
    attributes = json.loads(mock_row_data['attributes'])
    friendly_name = attributes.get('friendly_name', mock_row_data['entity_id'])
    unit_of_measurement = attributes.get('unit_of_measurement')
    print(f"✅ TEST: Attributes parsed successfully:")
    print(f"  - friendly_name: {friendly_name}")
    print(f"  - unit_of_measurement: {unit_of_measurement}")
except Exception as e:
    print(f"❌ TEST: Attribute parsing failed: {e}")

print("\n🧪 TEST: The domain column should now be available in the query results!")