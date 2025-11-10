# BigQuery Export Optimization Analysis
**Date:** 2025-11-10
**Purpose:** Analyze current export strategy and optimize for ML/analytics

---

## 📊 Current State Assessment

### What You're Exporting Now

**Schema:** Unified Timeline Model (states + events)
- ✅ States with attributes (sensor readings)
- ✅ Automation events
- ✅ Script events
- ✅ Scene activations
- ✅ Pre-computed time features (hour, day, season, etc.)
- ✅ Area/label metadata
- ✅ Context linking (tracks causality)

**Current Issues:**
1. **Network sensor noise** - Aggressive filtering in place but may still be too broad
2. **Missing your new 49 template sensors** - Not yet in export config
3. **Potential redundancy** - Some calculated sensors may duplicate raw data
4. **No humidity tracking** - Missing from time features
5. **Limited domain-specific features** - HVAC, air quality not optimized

---

## 🎯 What SHOULD Be Exported

### ✅ **High-Value Sensors for ML**

#### **HVAC & Climate (Top Priority)**
```yaml
# Raw measurements (must have)
- climate.thermostat_kitchen
- climate.thermostat_upstairs
- sensor.thermostat_kitchen_outdoor_temperature
- sensor.thermostat_upstairs_outdoor_temperature
- sensor.furnace_basement_power
- sensor.shelly_attic_hvac_power
- sensor.furnace_basement_energy
- sensor.shelly_attic_hvac_energy

# NEW: Template sensors (selective)
- sensor.hvac_power_draw_estimate_enhanced  # For prediction accuracy validation
- sensor.hvac_zone_balance                   # For efficiency analysis
- sensor.west_side_solar_heat_impact        # For solar gain tracking
- sensor.total_hvac_power                   # For overall consumption
- sensor.hvac_runtime_hours_today           # For runtime patterns
- sensor.daily_hvac_cost_estimate_heat_pump # For cost analysis

# NEW: Outdoor unit estimates (validation)
- sensor.basement_heat_pump_outdoor_power
- sensor.upstairs_heat_pump_outdoor_power
- sensor.basement_heat_pump_outdoor_energy
- sensor.upstairs_heat_pump_outdoor_energy
```

**Why:** HVAC is your biggest energy consumer. Track raw data + estimates for model training/validation.

#### **Temperature (High Value)**
```yaml
# Raw temperature sensors (all rooms)
- sensor.awair_temperature
- sensor.airthings_basement_temperature
- sensor.airthings_master_bedroom_temperature
- sensor.thermostat_kitchen_temperature
- sensor.multisensor_front_room_temperature
- sensor.temp_rh_sensor_master_bath_air_temperature
- sensor.temp_rh_sensor_kids_bathroom_air_temperature
- sensor.multisensor_basement_main_temperature

# NEW: Calculated metrics (export these)
- sensor.whole_house_average_temperature    # Summary metric
- sensor.temperature_stratification         # Comfort/efficiency indicator
- sensor.coldest_room                       # Diagnostic
- sensor.warmest_room                       # Diagnostic
```

**Why:** Temperature distribution = comfort + HVAC efficiency. Room-specific patterns matter.

#### **Air Quality (High Value)**
```yaml
# Raw measurements
- sensor.airthings_master_bedroom_carbon_dioxide
- sensor.airthings_basement_carbon_dioxide
- sensor.awair_co2
- sensor.airthings_master_bedroom_vocs
- sensor.airthings_basement_vocs
- sensor.awair_voc
- sensor.awair_pm2_5
- sensor.airthings_master_bedroom_radon
- sensor.airthings_basement_radon

# NEW: Composite scores (export for correlation analysis)
- sensor.whole_house_air_quality_score      # Overall metric
- sensor.air_quality_co2_score              # For threshold detection
- sensor.air_quality_voc_score
- sensor.air_quality_pm25_score
- sensor.air_quality_radon_score
- sensor.worst_air_quality_room             # Problem detection
```

**Why:** Air quality affects health + indicates HVAC ventilation effectiveness.

#### **Sleep & Comfort (Medium-High Value)**
```yaml
# NEW: Export these for behavior correlation
- sensor.bedroom_sleep_environment_score    # Sleep quality predictor
- sensor.house_comfort_index                # Overall comfort
- sensor.bedroom_window_status_inferred     # Behavior pattern
- sensor.ventilation_effectiveness_score    # Air circulation metric
```

**Why:** Correlate with HVAC usage, energy patterns, and occupancy.

#### **Weather (Essential Context)**
```yaml
- sensor.openweather3_temperature
- sensor.openweather3_humidity
- sensor.openweather3_pressure
- sensor.openweather3_wind_speed
- sensor.thermostat_kitchen_outdoor_humidity
- sensor.air_quality_index                  # Outdoor AQI
```

**Why:** Weather = primary driver of HVAC load and indoor conditions.

---

## ❌ What NOT to Export

### **Skip These Template Sensors (Redundant)**

```yaml
# Don't export - derive from raw data in BQ
- sensor.hvac_power_draw_estimate           # Keep only _enhanced version
- sensor.hvac_kitchen_zone_power_estimate   # Calculated, not measured
- sensor.hvac_upstairs_zone_power_estimate  # Calculated, not measured
- sensor.hvac_daily_energy_estimate         # Can derive from hourly data
- sensor.hvac_prediction_accuracy_*         # Calculate in BQ queries

# Don't export - extract from climate entities in BQ
- sensor.kitchen_fan_mode                   # Already in climate.thermostat_kitchen attributes
- sensor.upstairs_fan_mode                  # Already in climate.thermostat_upstairs attributes
- sensor.kitchen_humidity                   # Already in climate attributes
- sensor.upstairs_humidity                  # Already in climate attributes
- sensor.kitchen_temperature_error          # Calculate: current - setpoint
- sensor.upstairs_temperature_error         # Calculate: current - setpoint
```

**Why:** These can be calculated in BigQuery from raw data. No need to store twice.

### **Network Sensors (Already Filtered)**
Your current filters are good:
```python
EXCLUDE_NETWORK_PATTERNS = [
    'sensor.firewall_interface_',
    '_packets_per_second',
    '_kilobytes_per_second',
]
```

**Keep only:**
```yaml
- sensor.speedtest_download
- sensor.speedtest_upload
- sensor.wan_download_utilization
- sensor.wan_upload_utilization
```

---

## 🔧 Recommended Export Configuration

### **Add to allowed_entities in config:**

```yaml
bigquery_export:
  allowed_entities:
    # HVAC - Raw measurements
    - climate.thermostat_kitchen
    - climate.thermostat_upstairs
    - sensor.furnace_basement_power
    - sensor.shelly_attic_hvac_power
    - sensor.furnace_basement_energy
    - sensor.shelly_attic_hvac_energy

    # HVAC - Key template sensors
    - sensor.hvac_power_draw_estimate_enhanced
    - sensor.total_hvac_power
    - sensor.hvac_zone_balance
    - sensor.west_side_solar_heat_impact
    - sensor.hvac_runtime_hours_today
    - sensor.daily_hvac_cost_estimate_heat_pump
    - sensor.basement_heat_pump_outdoor_power
    - sensor.upstairs_heat_pump_outdoor_power
    - sensor.basement_heat_pump_outdoor_energy
    - sensor.upstairs_heat_pump_outdoor_energy

    # Temperature - All raw sensors
    - sensor.awair_temperature
    - sensor.airthings_basement_temperature
    - sensor.airthings_master_bedroom_temperature
    - sensor.thermostat_kitchen_temperature
    - sensor.thermostat_upstairs_temperature
    - sensor.multisensor_front_room_temperature
    - sensor.temp_rh_sensor_master_bath_air_temperature
    - sensor.temp_rh_sensor_kids_bathroom_air_temperature
    - sensor.multisensor_basement_main_temperature

    # Temperature - Key metrics
    - sensor.whole_house_average_temperature
    - sensor.temperature_stratification
    - sensor.coldest_room
    - sensor.warmest_room

    # Air Quality - Raw measurements
    - sensor.airthings_master_bedroom_carbon_dioxide
    - sensor.airthings_basement_carbon_dioxide
    - sensor.awair_co2
    - sensor.airthings_master_bedroom_vocs
    - sensor.airthings_basement_vocs
    - sensor.awair_voc
    - sensor.awair_pm2_5
    - sensor.awair_humidity
    - sensor.airthings_master_bedroom_radon
    - sensor.airthings_basement_radon
    - sensor.airthings_master_bedroom_humidity
    - sensor.airthings_basement_humidity

    # Air Quality - Composite scores
    - sensor.whole_house_air_quality_score
    - sensor.air_quality_co2_score
    - sensor.air_quality_voc_score
    - sensor.air_quality_pm25_score
    - sensor.air_quality_radon_score
    - sensor.whole_house_co2_average
    - sensor.worst_air_quality_room

    # Comfort & Sleep
    - sensor.bedroom_sleep_environment_score
    - sensor.house_comfort_index
    - sensor.bedroom_window_status_inferred
    - sensor.ventilation_effectiveness_score

    # Weather (context)
    - sensor.openweather3_temperature
    - sensor.openweather3_humidity
    - sensor.openweather3_pressure
    - sensor.openweather3_wind_speed
    - sensor.thermostat_kitchen_outdoor_temperature
    - sensor.thermostat_upstairs_outdoor_temperature
    - sensor.thermostat_kitchen_outdoor_humidity
    - sensor.air_quality_index

    # Network (essential only)
    - sensor.speedtest_download
    - sensor.speedtest_upload
    - sensor.wan_download_utilization
    - sensor.wan_upload_utilization
```

---

## 🧠 Feature Engineering Opportunities

### **1. HVAC Efficiency Score (Derived in BQ)**
```sql
WITH hvac_efficiency AS (
  SELECT
    timestamp,
    -- Actual vs Predicted Power
    (actual_power - predicted_power) / predicted_power AS prediction_error,

    -- Energy per degree-hour
    total_energy / (indoor_temp - outdoor_temp) AS energy_per_degree_hour,

    -- Zone balance score (0-100)
    100 - ABS(basement_power - upstairs_power) / (basement_power + upstairs_power) * 100 AS balance_score,

    -- Runtime efficiency (actual power / rated capacity)
    actual_power / 13.0 AS capacity_utilization
  FROM hvac_merged_data
)
```

**Use Case:** Detect HVAC performance degradation, optimize schedules

### **2. Comfort-Energy Trade-off (Derived in BQ)**
```sql
WITH comfort_cost AS (
  SELECT
    DATE(timestamp) as date,
    AVG(house_comfort_index) as avg_comfort,
    AVG(temperature_stratification) as avg_stratification,
    SUM(total_hvac_energy) as daily_energy,
    SUM(total_hvac_energy) * 0.12 as daily_cost
  FROM merged_data
  GROUP BY date
)
SELECT
  *,
  daily_energy / avg_comfort AS energy_per_comfort_point,
  CASE
    WHEN avg_comfort >= 70 AND daily_energy < 40 THEN 'Efficient'
    WHEN avg_comfort >= 70 AND daily_energy >= 40 THEN 'Comfortable_but_Expensive'
    WHEN avg_comfort < 70 AND daily_energy >= 40 THEN 'Inefficient'
    ELSE 'Needs_Improvement'
  END AS efficiency_category
FROM comfort_cost
```

**Use Case:** Optimize thermostat setpoints for cost/comfort balance

### **3. Sleep Quality Prediction Features**
```sql
SELECT
  timestamp,
  bedroom_sleep_environment_score,
  airthings_master_bedroom_carbon_dioxide,
  airthings_master_bedroom_temperature,
  bedroom_window_status_inferred,

  -- Derived features
  LAG(bedroom_sleep_environment_score, 1) OVER (ORDER BY timestamp) as prev_score,
  airthings_master_bedroom_carbon_dioxide - LAG(airthings_master_bedroom_carbon_dioxide, 1) OVER (ORDER BY timestamp) AS co2_trend,

  -- Night window (10pm - 6am)
  CASE WHEN EXTRACT(HOUR FROM timestamp) >= 22 OR EXTRACT(HOUR FROM timestamp) < 6 THEN 1 ELSE 0 END AS is_sleep_hours
FROM sensor_data
WHERE entity_id LIKE '%bedroom%'
```

**Use Case:** Predict sleep quality, trigger pre-sleep ventilation

### **4. Air Quality Event Detection**
```sql
WITH aq_spikes AS (
  SELECT
    timestamp,
    entity_id,
    state,
    state - LAG(state, 1) OVER (PARTITION BY entity_id ORDER BY timestamp) AS state_delta,
    AVG(state) OVER (PARTITION BY entity_id ORDER BY timestamp ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS moving_avg
  FROM sensor_data
  WHERE entity_id IN (
    'sensor.awair_co2',
    'sensor.awair_voc',
    'sensor.awair_pm2_5'
  )
)
SELECT
  *,
  CASE
    WHEN state_delta > 2 * STDDEV(state_delta) OVER (PARTITION BY entity_id) THEN 'Spike'
    WHEN state > moving_avg * 1.5 THEN 'High'
    ELSE 'Normal'
  END AS event_type
FROM aq_spikes
```

**Use Case:** Trigger ventilation, detect cooking events, alert on poor AQ

### **5. HVAC Load Forecasting Features**
```sql
SELECT
  timestamp,
  outdoor_temp,
  outdoor_humidity,
  wind_speed,
  house_avg_temp,
  total_hvac_power,

  -- Time features (already exported)
  hour_of_day,
  day_of_week,
  is_weekend,
  season,

  -- NEW: Weather lag features (for prediction)
  LAG(outdoor_temp, 1) OVER (ORDER BY timestamp) as outdoor_temp_1h_ago,
  LAG(outdoor_temp, 24) OVER (ORDER BY timestamp) as outdoor_temp_24h_ago,
  outdoor_temp - LAG(outdoor_temp, 1) OVER (ORDER BY timestamp) AS outdoor_temp_trend,

  -- NEW: Occupancy proxy (inferred from CO2)
  CASE WHEN whole_house_co2_average > 800 THEN 1 ELSE 0 END AS likely_occupied,

  -- NEW: Solar gain indicator
  CASE WHEN west_side_solar_heat_impact IN ('HIGH', 'MODERATE') THEN 1 ELSE 0 END AS solar_load
FROM merged_sensor_data
```

**Use Case:** Train ML model to predict HVAC load 1-4 hours ahead

---

## 📈 Schema Enhancements Needed

### **Add These Fields to BIGQUERY_SCHEMA:**

```python
# Add to const.py BIGQUERY_SCHEMA
{
    # Humidity tracking (missing!)
    {"name": "humidity", "type": "FLOAT", "mode": "NULLABLE"},

    # Numeric state for calculations
    {"name": "state_numeric", "type": "FLOAT", "mode": "NULLABLE"},

    # Delta from previous (for trend analysis)
    {"name": "state_delta", "type": "FLOAT", "mode": "NULLABLE"},

    # Device category (for filtering in BQ)
    {"name": "device_category", "type": "STRING", "mode": "NULLABLE"},  # hvac, air_quality, temperature, etc

    # Room/zone (for spatial analysis)
    {"name": "room", "type": "STRING", "mode": "NULLABLE"},  # Extract from friendly_name or area
}
```

### **Modify Export Logic to Populate:**

```python
# In services.py export function:

def extract_room_from_entity(entity_id, friendly_name, area_name):
    """Extract room/zone from entity metadata."""
    # Priority: area_name > friendly_name parsing > entity_id parsing
    if area_name:
        return area_name

    # Parse from friendly_name
    room_keywords = ['kitchen', 'basement', 'bedroom', 'master', 'bathroom', 'front', 'family']
    for keyword in room_keywords:
        if keyword in friendly_name.lower():
            return keyword.title()

    # Parse from entity_id
    for keyword in room_keywords:
        if keyword in entity_id.lower():
            return keyword.title()

    return "Unknown"

def categorize_device(entity_id, domain):
    """Categorize device for filtering."""
    if 'temperature' in entity_id or domain == 'climate':
        return 'temperature'
    elif any(x in entity_id for x in ['co2', 'voc', 'pm2_5', 'radon', 'air_quality']):
        return 'air_quality'
    elif any(x in entity_id for x in ['power', 'energy', 'hvac']):
        return 'hvac'
    elif any(x in entity_id for x in ['humidity']):
        return 'humidity'
    else:
        return 'other'
```

---

## 💾 Storage Optimization

### **Current Export Rate Estimate:**

Based on 49 template sensors + ~100 raw sensors = ~150 sensors

**State changes per day:**
- Temperature sensors: ~24/day (hourly) × 15 sensors = **360 records/day**
- HVAC sensors: ~288/day (5-min) × 10 sensors = **2,880 records/day**
- Air quality: ~24/day (hourly) × 15 sensors = **360 records/day**
- Weather: ~24/day × 5 sensors = **120 records/day**
- Composite scores: ~24/day × 15 sensors = **360 records/day**

**Total: ~4,080 state records/day = ~1.5M records/year**

### **With Events:**
- Automations: ~50-100/day
- Scripts: ~20-50/day
- Total events: ~100/day = **36K records/year**

### **Grand Total: ~1.54M records/year**

**Storage cost:** ~$10-15/year (BigQuery) + ~$1/month queries = **$22-28/year**

**Optimization:** ✅ Very reasonable! No need to reduce.

---

## 🎯 Action Items

### **Immediate (This Week):**
1. ✅ Add 49 new template sensors to `allowed_entities` config
2. ✅ Remove redundant template sensors (fan_mode, *_error) from export
3. ✅ Add humidity field to BigQuery schema
4. ✅ Add device_category and room fields to schema

### **Short Term (Next 2 Weeks):**
1. Verify all sensors exporting correctly
2. Run initial ML feature engineering queries in BQ
3. Create views for common analyses (HVAC efficiency, comfort score, etc.)
4. Set up BigQuery scheduled queries for daily aggregations

### **Medium Term (Next Month):**
1. Train HVAC load forecasting model
2. Implement sleep quality prediction
3. Build air quality alert thresholds
4. Create cost optimization recommendations

---

## 📊 Example Queries for Analysis

### **Query 1: Daily HVAC Efficiency Report**
```sql
WITH daily_hvac AS (
  SELECT
    DATE(timestamp) as date,
    AVG(CASE WHEN entity_id = 'sensor.whole_house_average_temperature' THEN SAFE_CAST(state AS FLOAT64) END) as avg_indoor_temp,
    AVG(CASE WHEN entity_id = 'sensor.thermostat_kitchen_outdoor_temperature' THEN SAFE_CAST(state AS FLOAT64) END) as avg_outdoor_temp,
    SUM(CASE WHEN entity_id LIKE '%hvac%energy' THEN SAFE_CAST(state AS FLOAT64) END) as total_energy,
    AVG(CASE WHEN entity_id = 'sensor.house_comfort_index' THEN SAFE_CAST(state AS FLOAT64) END) as avg_comfort,
    AVG(CASE WHEN entity_id = 'sensor.temperature_stratification' THEN SAFE_CAST(state AS FLOAT64) END) as avg_stratification
  FROM `project.dataset.sensor_data`
  WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  GROUP BY date
)
SELECT
  date,
  avg_indoor_temp,
  avg_outdoor_temp,
  ABS(avg_indoor_temp - avg_outdoor_temp) as temp_delta,
  total_energy,
  total_energy / ABS(avg_indoor_temp - avg_outdoor_temp) as energy_per_degree,
  avg_comfort,
  total_energy / avg_comfort as energy_per_comfort_point,
  avg_stratification
FROM daily_hvac
ORDER BY date DESC
```

### **Query 2: Room-Specific Air Quality Analysis**
```sql
SELECT
  area_name as room,
  AVG(CASE WHEN entity_id LIKE '%carbon_dioxide' THEN SAFE_CAST(state AS FLOAT64) END) as avg_co2,
  AVG(CASE WHEN entity_id LIKE '%vocs' THEN SAFE_CAST(state AS FLOAT64) END) as avg_voc,
  MAX(CASE WHEN entity_id LIKE '%carbon_dioxide' THEN SAFE_CAST(state AS FLOAT64) END) as max_co2,
  COUNT(CASE WHEN entity_id LIKE '%carbon_dioxide' AND SAFE_CAST(state AS FLOAT64) > 1000 THEN 1 END) as high_co2_count
FROM `project.dataset.sensor_data`
WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
  AND entity_id LIKE '%air%'
GROUP BY room
ORDER BY avg_co2 DESC
```

---

## 🏆 Expected Outcomes

**After 1 Month:**
- Baseline HVAC efficiency metrics established
- Comfort-cost trade-offs quantified
- Room-specific air quality patterns identified

**After 3 Months:**
- HVAC load forecasting model trained (90%+ accuracy)
- Sleep quality correlation with environment established
- Cost savings identified ($10-20/month potential)

**After 6 Months:**
- Automated HVAC optimization implemented
- Predictive air quality alerts active
- Total energy savings: 10-15%

---

**Last Updated:** 2025-11-10
**Next Review:** After 1 month of new sensor data collection
