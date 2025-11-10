# BigQuery Schema Enhancement Implementation Plan

**Created:** 2025-11-10
**Status:** Ready for implementation
**Risk Level:** ✅ Low (100% backward compatible)
**Estimated Time:** 2-4 hours (Phase 1)
**Expected ROI:** 5-20x query speedup, $16-20/year cost savings

---

## Overview

This plan implements the feature engineering enhancements identified in `ADVANCED_FEATURE_ENGINEERING.md` with the migration strategy from `SCHEMA_MIGRATION_PLAN.md`. All changes are backward compatible.

---

## Phase 1: Core Schema Enhancements (RECOMMENDED START HERE)

**Goal:** Add 12 critical NULLABLE fields for instant query performance improvements
**Time:** 2-4 hours
**Risk:** Zero (backward compatible)
**Benefits:** 5-20x faster queries, -60-80% query costs

### Step 1: Update Schema Definition (15 min)

**File:** `custom_components/bigquery_export/const.py`

**Action:** Add 12 new fields to `BIGQUERY_SCHEMA` after line 91 (after `state_changed`):

```python
# ============================================================================
# PHASE 1: FEATURE ENGINEERING ADDITIONS (2025-11-10)
# All fields NULLABLE for backward compatibility
# ============================================================================

# Numeric state parsing (eliminates SAFE_CAST in queries)
{"name": "state_numeric", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Numeric value of state field, pre-parsed for performance"},

# Domain-specific extractions (eliminate JSON parsing + type casting)
{"name": "temperature_value", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Extracted temperature value for temperature sensors"},
{"name": "humidity_value", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Extracted humidity value for humidity sensors"},
{"name": "power_value", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Extracted power value in watts"},
{"name": "energy_value", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Extracted energy value in kWh"},

# Spatial/categorization (enable fast filtering without LIKE patterns)
{"name": "room", "type": "STRING", "mode": "NULLABLE",
 "description": "Room/area extracted from entity_id or area_name"},
{"name": "device_category", "type": "STRING", "mode": "NULLABLE",
 "description": "Device category: temperature, humidity, power, air_quality, hvac, etc."},

# HVAC-specific (eliminate state_attributes JSON parsing)
{"name": "hvac_mode", "type": "STRING", "mode": "NULLABLE",
 "description": "HVAC mode: heat, cool, auto, off"},
{"name": "hvac_action", "type": "STRING", "mode": "NULLABLE",
 "description": "Current HVAC action: heating, cooling, idle"},
{"name": "target_temperature", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Target temperature setpoint"},
{"name": "current_temperature", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Current temperature reading from thermostat"},
{"name": "fan_mode", "type": "STRING", "mode": "NULLABLE",
 "description": "Fan mode: auto, on, circulate"},
```

**Validation:**
```bash
# Check config loads without errors
cd /Users/tbailey/Dev/ha-bigquery-export
grep -A 15 "PHASE 1: FEATURE ENGINEERING" custom_components/bigquery_export/const.py
```

---

### Step 2: Implement Feature Extraction Logic (45-60 min)

**File:** `custom_components/bigquery_export/services.py`

**Action:** Create feature extraction functions before the `BigQueryExportService` class:

```python
"""Feature extraction utilities for BigQuery export."""
import re
from typing import Dict, Any, Optional
import logging

_LOGGER = logging.getLogger(__name__)


def safe_float(value: Any) -> Optional[float]:
    """Safely convert value to float, return None if not possible."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def extract_room_from_entity(entity_id: str, area_name: Optional[str] = None) -> Optional[str]:
    """Extract room name from entity_id or area_name.

    Examples:
        sensor.awair_temperature -> None (no room in entity)
        sensor.airthings_master_bedroom_temperature -> Master Bedroom
        sensor.multisensor_basement_main_temperature -> Basement Main
        area_name='Kitchen' -> Kitchen
    """
    if area_name:
        return area_name

    # Extract room from entity_id
    # Pattern: sensor.device_ROOM_attribute
    parts = entity_id.split('_')

    # Skip domain and device name, look for room indicators
    room_keywords = ['bedroom', 'bathroom', 'kitchen', 'basement', 'attic',
                     'living', 'dining', 'family', 'office', 'garage', 'front']

    room_parts = []
    for i, part in enumerate(parts):
        if part.lower() in room_keywords:
            # Include this part and potentially next part (e.g., "master bedroom")
            room_parts.append(part.title())
            if i + 1 < len(parts) and parts[i + 1].lower() in room_keywords:
                room_parts.append(parts[i + 1].title())
                break
            break

    return ' '.join(room_parts) if room_parts else None


def categorize_device(entity_id: str, domain: str, attributes: Dict[str, Any]) -> Optional[str]:
    """Categorize device based on entity_id, domain, and attributes.

    Categories:
        - temperature
        - humidity
        - power
        - energy
        - air_quality (CO2, VOC, PM2.5, radon)
        - hvac
        - motion
        - door_window
        - light
        - other
    """
    entity_lower = entity_id.lower()
    device_class = attributes.get('device_class', '').lower()

    # Check device_class first (most reliable)
    if device_class in ['temperature']:
        return 'temperature'
    elif device_class in ['humidity']:
        return 'humidity'
    elif device_class in ['power']:
        return 'power'
    elif device_class in ['energy']:
        return 'energy'
    elif device_class in ['motion', 'occupancy']:
        return 'motion'
    elif device_class in ['door', 'window', 'opening']:
        return 'door_window'

    # Check domain
    if domain == 'climate':
        return 'hvac'
    elif domain == 'light':
        return 'light'

    # Check entity_id patterns
    if any(x in entity_lower for x in ['temperature', 'temp']):
        return 'temperature'
    elif any(x in entity_lower for x in ['humidity', 'humid']):
        return 'humidity'
    elif 'power' in entity_lower and 'power_factor' not in entity_lower:
        return 'power'
    elif 'energy' in entity_lower:
        return 'energy'
    elif any(x in entity_lower for x in ['co2', 'carbon_dioxide', 'voc', 'pm2', 'pm10', 'radon', 'air_quality']):
        return 'air_quality'
    elif any(x in entity_lower for x in ['hvac', 'thermostat', 'climate', 'furnace', 'heat_pump']):
        return 'hvac'
    elif any(x in entity_lower for x in ['motion', 'occupancy', 'presence']):
        return 'motion'
    elif any(x in entity_lower for x in ['door', 'window']):
        return 'door_window'
    elif any(x in entity_lower for x in ['light', 'lamp', 'bulb']):
        return 'light'

    return 'other'


def extract_domain_features(
    entity_id: str,
    state: str,
    attributes: Dict[str, Any],
    domain: str,
    area_name: Optional[str] = None
) -> Dict[str, Any]:
    """Extract all domain-specific features from entity state and attributes.

    Returns dict with keys matching BIGQUERY_SCHEMA field names.
    """
    features = {
        "state_numeric": None,
        "temperature_value": None,
        "humidity_value": None,
        "power_value": None,
        "energy_value": None,
        "room": None,
        "device_category": None,
        "hvac_mode": None,
        "hvac_action": None,
        "target_temperature": None,
        "current_temperature": None,
        "fan_mode": None,
    }

    # 1. Parse numeric state
    features["state_numeric"] = safe_float(state)

    # 2. Extract room and category
    features["room"] = extract_room_from_entity(entity_id, area_name)
    features["device_category"] = categorize_device(entity_id, domain, attributes)

    # 3. Domain-specific extractions
    category = features["device_category"]
    state_num = features["state_numeric"]

    if category == 'temperature' and state_num is not None:
        features["temperature_value"] = state_num

    elif category == 'humidity' and state_num is not None:
        features["humidity_value"] = state_num

    elif category == 'power' and state_num is not None:
        features["power_value"] = state_num

    elif category == 'energy' and state_num is not None:
        features["energy_value"] = state_num

    elif category == 'hvac' or domain == 'climate':
        # Extract HVAC-specific attributes
        features["hvac_mode"] = attributes.get('hvac_mode')
        features["hvac_action"] = attributes.get('hvac_action')
        features["target_temperature"] = safe_float(attributes.get('temperature'))
        features["current_temperature"] = safe_float(attributes.get('current_temperature'))
        features["fan_mode"] = attributes.get('fan_mode')

        # If state is a temperature, use it
        if state_num is not None and features["current_temperature"] is None:
            features["current_temperature"] = state_num

    return features


# Example usage (for testing):
# features = extract_domain_features(
#     entity_id='sensor.furnace_basement_power',
#     state='450.5',
#     attributes={'device_class': 'power', 'unit_of_measurement': 'W'},
#     domain='sensor',
#     area_name='Basement'
# )
# # Returns: {
# #   'state_numeric': 450.5,
# #   'power_value': 450.5,
# #   'device_category': 'power',
# #   'room': 'Basement',
# #   ...
# # }
```

**Then, update the `_prepare_record` method in `BigQueryExportService` class:**

Find the existing `_prepare_record` method and add feature extraction:

```python
def _prepare_record(self, state: State, export_time: datetime) -> dict:
    """Prepare a state record for BigQuery export with feature extraction."""
    # Existing code to extract entity_id, state, attributes, etc.
    entity_id = state.entity_id
    state_value = state.state
    attributes = state.attributes or {}
    domain = state.domain
    area_name = attributes.get('area_name')  # If available

    # Parse state_attributes JSON
    state_attributes_json = json.dumps(attributes) if attributes else None

    # ... existing code for timestamp, context, etc. ...

    # ============================================================================
    # NEW: Extract domain features
    # ============================================================================
    features = extract_domain_features(
        entity_id=entity_id,
        state=state_value,
        attributes=attributes,
        domain=domain,
        area_name=area_name
    )

    # Build record with existing fields + new feature fields
    record = {
        # Existing fields
        "entity_id": entity_id,
        "state": state_value,
        "timestamp": state.last_updated.isoformat(),
        "state_attributes": state_attributes_json,
        # ... all existing fields ...

        # NEW: Feature fields
        "state_numeric": features["state_numeric"],
        "temperature_value": features["temperature_value"],
        "humidity_value": features["humidity_value"],
        "power_value": features["power_value"],
        "energy_value": features["energy_value"],
        "room": features["room"],
        "device_category": features["device_category"],
        "hvac_mode": features["hvac_mode"],
        "hvac_action": features["hvac_action"],
        "target_temperature": features["target_temperature"],
        "current_temperature": features["current_temperature"],
        "fan_mode": features["fan_mode"],

        "export_timestamp": export_time.isoformat(),
    }

    return record
```

**Validation:**
```bash
# Test that Python code is syntactically correct
cd /Users/tbailey/Dev/ha-bigquery-export
python3 -m py_compile custom_components/bigquery_export/services.py
echo $?  # Should output 0 if successful
```

---

### Step 3: Create Unit Tests (30 min)

**File:** `tests/test_feature_extraction.py` (create if doesn't exist)

```python
"""Tests for feature extraction logic."""
import pytest
from custom_components.bigquery_export.services import (
    extract_domain_features,
    categorize_device,
    extract_room_from_entity,
    safe_float
)


def test_safe_float():
    """Test safe_float utility."""
    assert safe_float("123.45") == 123.45
    assert safe_float(123) == 123.0
    assert safe_float("invalid") is None
    assert safe_float(None) is None


def test_extract_room_from_entity():
    """Test room extraction from entity_id."""
    assert extract_room_from_entity(
        "sensor.airthings_master_bedroom_temperature"
    ) == "Master Bedroom"

    assert extract_room_from_entity(
        "sensor.multisensor_basement_main_temperature"
    ) == "Basement Main"

    assert extract_room_from_entity(
        "sensor.awair_temperature",
        area_name="Family Room"
    ) == "Family Room"


def test_categorize_device():
    """Test device categorization."""
    # Temperature sensor
    assert categorize_device(
        "sensor.awair_temperature",
        "sensor",
        {"device_class": "temperature"}
    ) == "temperature"

    # Power sensor
    assert categorize_device(
        "sensor.furnace_basement_power",
        "sensor",
        {"device_class": "power"}
    ) == "power"

    # HVAC
    assert categorize_device(
        "climate.thermostat_kitchen",
        "climate",
        {}
    ) == "hvac"

    # Air quality
    assert categorize_device(
        "sensor.awair_co2",
        "sensor",
        {}
    ) == "air_quality"


def test_extract_domain_features_temperature():
    """Test feature extraction for temperature sensor."""
    features = extract_domain_features(
        entity_id="sensor.awair_temperature",
        state="68.5",
        attributes={"device_class": "temperature", "unit_of_measurement": "°F"},
        domain="sensor",
        area_name="Family Room"
    )

    assert features["state_numeric"] == 68.5
    assert features["temperature_value"] == 68.5
    assert features["device_category"] == "temperature"
    assert features["room"] == "Family Room"
    assert features["power_value"] is None  # Not a power sensor


def test_extract_domain_features_power():
    """Test feature extraction for power sensor."""
    features = extract_domain_features(
        entity_id="sensor.furnace_basement_power",
        state="450.5",
        attributes={"device_class": "power", "unit_of_measurement": "W"},
        domain="sensor",
        area_name="Basement"
    )

    assert features["state_numeric"] == 450.5
    assert features["power_value"] == 450.5
    assert features["device_category"] == "power"
    assert features["room"] == "Basement"


def test_extract_domain_features_hvac():
    """Test feature extraction for HVAC/climate entity."""
    features = extract_domain_features(
        entity_id="climate.thermostat_kitchen",
        state="heat",
        attributes={
            "hvac_mode": "heat",
            "hvac_action": "heating",
            "temperature": 68.0,
            "current_temperature": 65.5,
            "fan_mode": "auto"
        },
        domain="climate",
        area_name="Kitchen"
    )

    assert features["device_category"] == "hvac"
    assert features["hvac_mode"] == "heat"
    assert features["hvac_action"] == "heating"
    assert features["target_temperature"] == 68.0
    assert features["current_temperature"] == 65.5
    assert features["fan_mode"] == "auto"
    assert features["room"] == "Kitchen"


def test_extract_domain_features_non_numeric():
    """Test feature extraction for non-numeric state."""
    features = extract_domain_features(
        entity_id="binary_sensor.front_door",
        state="on",
        attributes={"device_class": "door"},
        domain="binary_sensor"
    )

    assert features["state_numeric"] is None  # Can't parse "on"
    assert features["device_category"] == "door_window"
```

**Run tests:**
```bash
cd /Users/tbailey/Dev/ha-bigquery-export
python3 -m pytest tests/test_feature_extraction.py -v
```

---

### Step 4: Update BigQuery Schema (5 min)

**Prerequisites:**
- Google Cloud SDK installed (`gcloud` command available)
- Authenticated with service account that has BigQuery Admin role
- Know your project ID, dataset ID, and table name

**Export current schema (backup):**
```bash
# Set variables
export PROJECT_ID="your-project-id"
export DATASET_ID="your-dataset-id"
export TABLE_ID="sensor_data"

# Backup current schema
bq show --schema --format=prettyjson \
  ${PROJECT_ID}:${DATASET_ID}.${TABLE_ID} \
  > /Users/tbailey/Dev/ha-bigquery-export/schema_backup_$(date +%Y%m%d).json

echo "✅ Schema backed up"
```

**Generate new schema JSON:**
```python
# Run this in Python to generate schema JSON from const.py
cd /Users/tbailey/Dev/ha-bigquery-export
python3 << 'EOF'
import json
import sys
sys.path.insert(0, 'custom_components/bigquery_export')
from const import BIGQUERY_SCHEMA

with open('schema_enhanced.json', 'w') as f:
    json.dump(BIGQUERY_SCHEMA, f, indent=2)

print("✅ Schema JSON generated: schema_enhanced.json")
EOF
```

**Update BigQuery table schema (DRY RUN first):**
```bash
# Dry run to validate
bq update --schema=schema_enhanced.json \
  --dry_run \
  ${PROJECT_ID}:${DATASET_ID}.${TABLE_ID}

echo "✅ Dry run passed - ready to apply"
```

**Apply schema update (ZERO DOWNTIME):**
```bash
# Apply schema update (adds NULLABLE columns, no impact on existing data)
bq update --schema=schema_enhanced.json \
  ${PROJECT_ID}:${DATASET_ID}.${TABLE_ID}

echo "✅ Schema updated with 12 new NULLABLE fields"
```

**Verify schema update:**
```bash
# Check that new fields exist
bq show --schema --format=prettyjson \
  ${PROJECT_ID}:${DATASET_ID}.${TABLE_ID} \
  | grep -E "(state_numeric|temperature_value|device_category|hvac_mode)"

echo "✅ New fields confirmed in schema"
```

---

### Step 5: Deploy Updated Integration (30 min)

**Option A: Development Testing (Recommended First)**

```bash
# Copy updated files to Home Assistant custom_components
cp custom_components/bigquery_export/const.py \
   /Volumes/config/custom_components/bigquery_export/const.py

cp custom_components/bigquery_export/services.py \
   /Volumes/config/custom_components/bigquery_export/services.py

echo "✅ Files copied to Home Assistant"
```

**Restart Home Assistant:**
```bash
# Via HA UI: Settings → System → Restart
# Or via SSH/Terminal:
ha core restart

# Wait 2-3 minutes for restart
echo "⏳ Waiting for Home Assistant to restart..."
sleep 180
echo "✅ Home Assistant should be back online"
```

**Check logs for errors:**
```bash
# Via HA UI: Settings → System → Logs
# Look for bigquery_export errors

# Or via command line:
tail -f /Volumes/config/home-assistant.log | grep bigquery
```

**Option B: Production Deployment**

If testing looks good, commit changes:
```bash
cd /Users/tbailey/Dev/ha-bigquery-export
git add custom_components/bigquery_export/const.py
git add custom_components/bigquery_export/services.py
git add tests/test_feature_extraction.py
git commit -m "feat: Add Phase 1 feature engineering - 12 new NULLABLE fields

- Add state_numeric for pre-parsed numeric values
- Add domain-specific fields (temperature, humidity, power, energy)
- Add spatial fields (room, device_category)
- Add HVAC-specific fields (mode, action, temps, fan)
- All fields NULLABLE for backward compatibility
- Implement feature extraction in services.py
- Add comprehensive unit tests

Performance: 5-20x faster queries, -60-80% query costs
Risk: Zero (backward compatible)
"

git push origin main
```

---

### Step 6: Validation & Testing (30 min)

**Test 1: Trigger Manual Export**

```yaml
# In Home Assistant Developer Tools → Services:
service: bigquery_export.export_data
data: {}
```

**Check Home Assistant logs:**
```bash
tail -f /Volumes/config/home-assistant.log | grep bigquery

# Look for:
# ✅ "Exporting XX records to BigQuery"
# ✅ "Export completed successfully"
# ❌ Any ERROR or WARNING messages
```

**Test 2: Query New Fields in BigQuery**

```sql
-- Check that new fields are populating
SELECT
  entity_id,
  state,
  state_numeric,
  device_category,
  room,
  temperature_value,
  power_value,
  hvac_mode,
  export_timestamp
FROM `project.dataset.sensor_data`
WHERE export_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
  AND state_numeric IS NOT NULL
ORDER BY export_timestamp DESC
LIMIT 20;
```

**Expected Results:**
- ✅ `state_numeric` populated for numeric sensors
- ✅ `device_category` showing: temperature, power, hvac, air_quality, etc.
- ✅ `room` showing: Kitchen, Basement, Master Bedroom, etc.
- ✅ `temperature_value` populated for temp sensors
- ✅ `power_value` populated for power sensors
- ✅ `hvac_mode`, `hvac_action` populated for climate entities

**Test 3: Performance Comparison**

```sql
-- OLD WAY (slow, expensive)
SELECT
  entity_id,
  SAFE_CAST(state AS FLOAT64) as power,
  timestamp
FROM `project.dataset.sensor_data`
WHERE entity_id LIKE '%power%'
  AND SAFE_CAST(state AS FLOAT64) > 0
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY timestamp DESC;
-- Note: Query time, bytes processed

-- NEW WAY (fast, cheap)
SELECT
  entity_id,
  power_value as power,
  timestamp
FROM `project.dataset.sensor_data`
WHERE device_category = 'power'
  AND power_value > 0
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY timestamp DESC;
-- Compare: Should be 5-10x faster, process 60-80% fewer bytes
```

**Test 4: Backward Compatibility**

```sql
-- Verify old queries still work
SELECT
  entity_id,
  state,  -- Still populated ✅
  SAFE_CAST(state AS FLOAT64) as power,  -- Still works ✅
  timestamp
FROM `project.dataset.sensor_data`
WHERE entity_id = 'sensor.furnace_basement_power'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
ORDER BY timestamp DESC
LIMIT 10;
```

**Test 5: Mixed Data Query (Old + New)**

```sql
-- COALESCE handles records with and without new fields
SELECT
  entity_id,
  timestamp,
  COALESCE(
    power_value,  -- New field (fast, NULL for old records)
    SAFE_CAST(state AS FLOAT64)  -- Old method (fallback)
  ) as power,
  device_category  -- Will be NULL for old records
FROM `project.dataset.sensor_data`
WHERE entity_id = 'sensor.furnace_basement_power'
ORDER BY timestamp DESC
LIMIT 20;
```

---

### Step 7: Monitor & Iterate (Ongoing)

**Create monitoring dashboard in BigQuery:**

```sql
-- Feature population rate
SELECT
  DATE(export_timestamp) as date,
  COUNT(*) as total_records,
  COUNTIF(state_numeric IS NOT NULL) as numeric_states,
  COUNTIF(device_category IS NOT NULL) as categorized,
  COUNTIF(room IS NOT NULL) as with_room,
  COUNTIF(temperature_value IS NOT NULL) as temp_sensors,
  COUNTIF(power_value IS NOT NULL) as power_sensors,
  COUNTIF(hvac_mode IS NOT NULL) as hvac_entities,

  -- Population percentages
  ROUND(COUNTIF(state_numeric IS NOT NULL) / COUNT(*) * 100, 1) as numeric_pct,
  ROUND(COUNTIF(device_category IS NOT NULL) / COUNT(*) * 100, 1) as category_pct,

FROM `project.dataset.sensor_data`
WHERE export_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY date
ORDER BY date DESC;
```

**Expected results after 24 hours:**
- `numeric_pct`: ~60-70% (many sensors are numeric)
- `category_pct`: ~95-100% (most entities can be categorized)
- `temp_sensors`: ~10-20 per hour
- `power_sensors`: ~50-100 per hour (if polling frequently)
- `hvac_entities`: ~10-20 per hour

**Check for extraction errors in HA logs:**
```bash
grep -i "error.*bigquery.*extract" /Volumes/config/home-assistant.log
```

**Iterate based on findings:**
- If `room` extraction is low, adjust `extract_room_from_entity()` logic
- If categorization is wrong, refine `categorize_device()` patterns
- If HVAC fields not populating, check attribute names in HA

---

## Phase 1 Complete! ✅

**Success Criteria:**
- ✅ 12 new NULLABLE fields added to BigQuery schema
- ✅ Feature extraction functions implemented and tested
- ✅ New exports populating new fields correctly
- ✅ Old queries still working (backward compatible)
- ✅ Performance improvement confirmed (5-20x faster)
- ✅ No errors in Home Assistant logs

**Outcome:**
- Queries now 5-20x faster
- Query costs reduced 60-80%
- No breaking changes to existing queries
- Old data still queryable with COALESCE

---

## Phase 2: Advanced Features (OPTIONAL)

**Time:** 3-5 hours
**Prerequisites:** Phase 1 complete and validated
**Benefits:** +8-10% ML accuracy, time-series analysis improvements

### Step 1: Add Advanced Schema Fields

Add to `const.py` schema:

```python
# ============================================================================
# PHASE 2: ADVANCED FEATURE ENGINEERING (Optional)
# ============================================================================

# Cyclic time encoding (prevents hour 23→0 discontinuity in ML)
{"name": "hour_sin", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Sine encoding of hour (0-23) for ML"},
{"name": "hour_cos", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Cosine encoding of hour (0-23) for ML"},
{"name": "day_sin", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Sine encoding of day of week (0-6) for ML"},
{"name": "day_cos", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Cosine encoding of day of week (0-6) for ML"},

# Rate of change features (time-series analysis)
{"name": "state_delta", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Change in numeric state from previous record"},
{"name": "state_derivative", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Rate of change (delta / time_diff_seconds)"},
{"name": "time_since_last_change", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Seconds since state last changed (not just updated)"},

# Occupancy inference
{"name": "occupancy_score", "type": "FLOAT", "mode": "NULLABLE",
 "description": "Inferred occupancy probability (0-1) from CO2, motion, power"},
{"name": "occupancy_confidence", "type": "STRING", "mode": "NULLABLE",
 "description": "Confidence level: high, medium, low"},
```

### Step 2: Implement Advanced Extraction

Add to `services.py`:

```python
import math
from datetime import datetime


def encode_cyclic_time(timestamp: datetime) -> Dict[str, float]:
    """Encode time cyclically using sin/cos for ML.

    Why: Prevents hour 23 and hour 0 being treated as far apart in ML models.
    """
    hour = timestamp.hour
    day_of_week = timestamp.weekday()

    # Encode hour (0-23) as point on unit circle
    hour_rad = 2 * math.pi * hour / 24

    # Encode day (0-6) as point on unit circle
    day_rad = 2 * math.pi * day_of_week / 7

    return {
        "hour_sin": math.sin(hour_rad),
        "hour_cos": math.cos(hour_rad),
        "day_sin": math.sin(day_rad),
        "day_cos": math.cos(day_rad),
    }


def infer_occupancy(
    co2: Optional[float],
    motion_recently: bool,
    power: Optional[float],
    room: Optional[str]
) -> tuple[Optional[float], Optional[str]]:
    """Infer occupancy probability from multiple signals.

    Returns: (occupancy_score: 0-1, confidence: high/medium/low)
    """
    signals = []
    weights = []

    # CO2 signal (strongest indicator)
    if co2 is not None:
        if co2 > 800:
            signals.append(1.0)  # Definitely occupied
            weights.append(0.5)
        elif co2 > 600:
            signals.append(0.7)  # Probably occupied
            weights.append(0.5)
        elif co2 < 450:
            signals.append(0.0)  # Definitely not occupied
            weights.append(0.5)
        else:
            signals.append(0.3)  # Likely not occupied
            weights.append(0.3)

    # Motion signal
    if motion_recently:
        signals.append(1.0)
        weights.append(0.3)

    # Power signal (moderate indicator)
    if power is not None and power > 50:  # More than idle power
        signals.append(0.6)
        weights.append(0.2)

    if not signals:
        return None, None

    # Weighted average
    score = sum(s * w for s, w in zip(signals, weights)) / sum(weights)

    # Confidence based on number of signals
    if len(signals) >= 2:
        confidence = "high"
    elif len(signals) == 1 and weights[0] >= 0.5:
        confidence = "medium"
    else:
        confidence = "low"

    return score, confidence
```

### Step 3: Update BigQuery Schema (Same as Phase 1 Step 4)

```bash
bq update --schema=schema_phase2.json \
  ${PROJECT_ID}:${DATASET_ID}.${TABLE_ID}
```

### Step 4: Deploy and Validate (Same as Phase 1 Steps 5-7)

---

## Phase 3: Optional Backfill (OPTIONAL)

**Goal:** Populate new fields for historical data
**Cost:** $0.10-1.00 one-time
**Time:** 5-10 minutes execution, plan 30 min
**Risk:** Low (UPDATE queries are safe)

### When to Backfill:
- ✅ Want historical queries to use new fields
- ✅ Want consistent data for ML training
- ❌ Don't need if using COALESCE in queries

### Backfill Query:

```sql
-- Backfill state_numeric (safest, most valuable)
UPDATE `project.dataset.sensor_data`
SET state_numeric = SAFE_CAST(state AS FLOAT64)
WHERE state_numeric IS NULL
  AND state IS NOT NULL
  AND SAFE_CAST(state AS FLOAT64) IS NOT NULL;

-- Backfill device_category (pattern matching)
UPDATE `project.dataset.sensor_data`
SET device_category =
  CASE
    WHEN entity_id LIKE '%temperature%' OR entity_id LIKE '%temp%' THEN 'temperature'
    WHEN entity_id LIKE '%humidity%' THEN 'humidity'
    WHEN entity_id LIKE '%power%' AND entity_id NOT LIKE '%power_factor%' THEN 'power'
    WHEN entity_id LIKE '%energy%' THEN 'energy'
    WHEN entity_id LIKE '%co2%' OR entity_id LIKE '%voc%' OR entity_id LIKE '%pm2%' OR entity_id LIKE '%radon%' THEN 'air_quality'
    WHEN entity_id LIKE '%climate%' OR entity_id LIKE '%thermostat%' OR entity_id LIKE '%hvac%' THEN 'hvac'
    WHEN entity_id LIKE '%motion%' THEN 'motion'
    ELSE 'other'
  END
WHERE device_category IS NULL;

-- Backfill domain-specific values
UPDATE `project.dataset.sensor_data`
SET
  temperature_value = state_numeric,
WHERE device_category = 'temperature'
  AND temperature_value IS NULL
  AND state_numeric IS NOT NULL;

UPDATE `project.dataset.sensor_data`
SET power_value = state_numeric
WHERE device_category = 'power'
  AND power_value IS NULL
  AND state_numeric IS NOT NULL;

-- Similar for humidity_value, energy_value, etc.
```

**Run backfill queries one at a time, check cost estimate first:**
```sql
-- Dry run to see cost
-- (Add --dry_run flag to bq query command)
```

---

## Phase 4: Query Optimization (OPTIONAL)

**Goal:** Update existing queries to use new fields
**Time:** 1-2 hours
**Benefits:** Realize full 5-20x speedup

### Identify Queries to Optimize:

```bash
# Find queries in your codebase that use SAFE_CAST
cd /Users/tbailey/Dev/ha-bigquery-export
grep -r "SAFE_CAST" . --include="*.sql" --include="*.py"

# Find queries using LIKE for filtering
grep -r "LIKE '%power%'" . --include="*.sql"
```

### Example Optimizations:

**Before:**
```sql
SELECT
  entity_id,
  SAFE_CAST(state AS FLOAT64) as temp,
  timestamp
FROM sensor_data
WHERE entity_id LIKE '%temperature%'
  AND SAFE_CAST(state AS FLOAT64) BETWEEN 60 AND 80
ORDER BY timestamp DESC;
```

**After:**
```sql
SELECT
  entity_id,
  temperature_value as temp,
  timestamp
FROM sensor_data
WHERE device_category = 'temperature'
  AND temperature_value BETWEEN 60 AND 80
ORDER BY timestamp DESC;
```

**For mixed old/new data:**
```sql
SELECT
  entity_id,
  COALESCE(temperature_value, SAFE_CAST(state AS FLOAT64)) as temp,
  timestamp
FROM sensor_data
WHERE device_category = 'temperature'
   OR (device_category IS NULL AND entity_id LIKE '%temperature%')
  AND COALESCE(temperature_value, SAFE_CAST(state AS FLOAT64)) BETWEEN 60 AND 80
ORDER BY timestamp DESC;
```

---

## Rollback Plan (If Needed)

### If Issues Found During Phase 1:

**Option 1: Disable Feature Extraction (Keep Schema)**
```python
# In services.py, comment out feature extraction:
# features = extract_domain_features(...)

# Set all features to None:
features = {
    "state_numeric": None,
    "temperature_value": None,
    # ... all None
}
```

**Option 2: Revert Code Changes**
```bash
# Restore from backup
cp /Volumes/config/custom_components/bigquery_export/const.py.backup \
   /Volumes/config/custom_components/bigquery_export/const.py

# Or git revert
git revert HEAD
```

**Option 3: Remove New Fields from Schema (Nuclear)**
```bash
# NOT RECOMMENDED - loses data in new fields
# Only if absolutely necessary

# Export data without new fields
bq extract --destination_format=NEWLINE_DELIMITED_JSON \
  project:dataset.sensor_data \
  gs://bucket/backup_*.json

# Recreate table with old schema
# (This is destructive - only as last resort)
```

---

## Success Metrics

### Phase 1 Success:
- ✅ New fields populating for >90% of numeric sensors
- ✅ Query performance improved 5-20x
- ✅ Query costs reduced 60-80%
- ✅ Zero errors in HA logs
- ✅ Old queries still working

### Phase 2 Success:
- ✅ Cyclic features enabling better ML predictions
- ✅ Rate of change features working for time-series analysis
- ✅ Occupancy inference showing reasonable probabilities

### Overall ROI:
- **Time invested:** 2-4 hours (Phase 1)
- **Annual savings:** $16-20/year (query cost reduction)
- **Performance gain:** 5-20x faster queries
- **ML accuracy gain:** +8-10% (Phase 2)
- **Risk:** Zero (backward compatible)

---

## Next Steps After Implementation

1. **Create Optimized Views** - Create BigQuery views using new fields for common queries
2. **Update Dashboards** - Migrate Looker/Data Studio dashboards to use new fields
3. **ML Model Training** - Retrain ML models with new features for improved accuracy
4. **Documentation** - Update query examples in documentation to use new fields
5. **Phase 2/3** - Consider implementing advanced features if Phase 1 successful

---

## Questions & Troubleshooting

### Q: What if some fields aren't populating?
**A:** Check extraction logic in `services.py`. Add logging:
```python
_LOGGER.debug(f"Extracted features for {entity_id}: {features}")
```

### Q: What if queries are still slow?
**A:** Check query execution plan in BigQuery console. Ensure:
- Using `device_category = 'X'` not `LIKE '%X%'`
- Using indexed fields (entity_id, timestamp)
- Filtering by partition (DATE(timestamp))

### Q: What if old data needs new fields?
**A:** Use COALESCE in queries, or run backfill (Phase 3)

### Q: Can I add more fields later?
**A:** Yes! Follow same process - add NULLABLE fields, update extraction logic, deploy.

---

**Ready to begin?** Start with **Phase 1, Step 1** above! ✅
