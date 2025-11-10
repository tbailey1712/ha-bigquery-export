# Installation Guide - Complete Sensor Setup

**Created:** 2025-11-09
**Purpose:** Clean directory-based template sensor installation

---

## 📁 What Was Created

### Directory: `configuration-template-addons/`

Contains 6 organized YAML files:

1. **01_hvac_power_estimates.yaml** - Your existing deployed sensors (11)
2. **02_hvac_outdoor_units.yaml** - NEW outdoor compressor estimates (2)
3. **03_hvac_attributes.yaml** - Fan mode, temp, humidity extraction (14)
4. **04_temperature_analysis.yaml** - Multi-room temp tracking (6)
5. **05_air_quality.yaml** - CO2, VOC, PM2.5, Radon scoring (9)
6. **06_sleep_comfort.yaml** - Sleep environment & comfort (7)

**Total: 49 template sensors**

### Supporting Files:

- `CONFIGURATION_YAML_ADDITIONS.yaml` - Copy-paste snippets for configuration.yaml
- `INSTALLATION_GUIDE.md` - This file
- `configuration-template-addons/README.md` - Detailed directory documentation

---

## 🚀 Quick Installation (3 Steps)

### Step 1: Add ONE Line to configuration.yaml

```yaml
template: !include_dir_merge_list configuration-template-addons/
```

### Step 2: Add Integration Platform to configuration.yaml

Add under your `sensor:` section (or create one):

```yaml
sensor:
  - platform: integration
    source: sensor.basement_heat_pump_outdoor_power
    name: "Basement Heat Pump Outdoor Energy"
    unique_id: basement_heat_pump_outdoor_energy
    unit_prefix: k
    unit_time: h
    method: left
    round: 2

  - platform: integration
    source: sensor.upstairs_heat_pump_outdoor_power
    name: "Upstairs Heat Pump Outdoor Energy"
    unique_id: upstairs_heat_pump_outdoor_energy
    unit_prefix: k
    unit_time: h
    method: left
    round: 2
```

### Step 3: Check, Restart, Wait

```bash
# 1. Check configuration
Developer Tools → YAML → Check Configuration

# 2. Restart Home Assistant
Developer Tools → YAML → Restart

# 3. Wait 2 hours for integration sensors to accumulate kWh data
```

---

## 📊 Add to Energy Dashboard (After 2 Hours)

Go to: **Settings → Dashboards → Energy → Individual Devices → Add Consumption**

Add these **4 sensors** (one at a time):

1. `sensor.furnace_basement_energy` (existing - indoor air handler)
2. `sensor.basement_heat_pump_outdoor_energy` (NEW - outdoor compressor)
3. `sensor.shelly_attic_hvac_energy` (existing - indoor air handler)
4. `sensor.upstairs_heat_pump_outdoor_energy` (NEW - outdoor compressor)

### Expected Result:

```
Your Energy Dashboard will show:
├─ 🟨 HVAC (Basement - Indoor)     ~2.5 kWh/day
├─ 🟧 HVAC (Basement - Outdoor)   ~18.0 kWh/day  ← NEW!
├─ 🟦 HVAC (Attic - Indoor)        ~2.7 kWh/day
├─ 🟪 HVAC (Attic - Outdoor)      ~20.0 kWh/day  ← NEW!
├─ 🟩 Dishwasher                   ~1.2 kWh/day
├─ 🟥 Bathroom Heated Floor        ~0.8 kWh/day
├─ ⬜ Lomi                          ~0.5 kWh/day
├─ 🔵 Kitchen LED                  ~0.3 kWh/day
└─ 🟫 Grow Tent                    ~2.0 kWh/day

Total HVAC: ~43 kWh/day (realistic!)
```

---

## ✅ Verification Checklist

### After Restart (Immediate):

- [ ] Check logs for errors: Settings → System → Logs
- [ ] Verify template sensors loaded: Developer Tools → States → Search "sensor."
- [ ] Check HVAC power estimates exist: `sensor.hvac_power_draw_estimate_enhanced`
- [ ] Check outdoor unit power sensors exist: `sensor.basement_heat_pump_outdoor_power`
- [ ] Check fan mode sensors exist: `sensor.kitchen_fan_mode`

### After 2 Hours:

- [ ] Verify energy sensors exist: `sensor.basement_heat_pump_outdoor_energy`
- [ ] Check energy values are accumulating (not zero)
- [ ] Test adding to Energy dashboard (should appear in list)

### After 24 Hours:

- [ ] Energy dashboard shows graphs
- [ ] All 4 HVAC sensors showing stacked bars
- [ ] BigQuery export contains new sensors

---

## 🔧 Optional: Add Utility Meters

If you want daily/monthly counters that reset, add to configuration.yaml:

```yaml
utility_meter:
  basement_heat_pump_outdoor_daily:
    source: sensor.basement_heat_pump_outdoor_energy
    name: "Basement Heat Pump Outdoor Daily"
    cycle: daily

  upstairs_heat_pump_outdoor_daily:
    source: sensor.upstairs_heat_pump_outdoor_energy
    name: "Upstairs Heat Pump Outdoor Daily"
    cycle: daily
```

---

## 📋 What Each Sensor Does

### HVAC Power & Energy (13 sensors)
- **Power Draw Estimates**: Predict HVAC power based on outdoor temp
- **Outdoor Unit Estimates**: Estimate compressor power for Energy dashboard
- **Prediction Accuracy**: Compare estimates to actual usage
- **Runtime Tracking**: Hours HVAC ran today

### HVAC Attributes (14 sensors)
- **Fan Mode**: Extract fan settings (on/auto) for BigQuery tracking
- **Temperature/Humidity**: Extract values from climate entities
- **Temperature Error**: How far off setpoint
- **System Efficiency**: How well HVAC maintains setpoint

### Temperature (6 sensors)
- **Average/Stratification**: Whole house temperature tracking
- **Coldest/Warmest Room**: Identify problem areas
- **Solar Heat Impact**: Afternoon west-side heating
- **Zone Balance**: Basement vs upstairs power distribution

### Air Quality (9 sensors)
- **CO2 Tracking**: Bedroom, basement, family room
- **Comprehensive Scoring**: Weighted air quality score (CO2, VOC, PM2.5, Radon)
- **Component Scores**: Individual pollutant tracking
- **Indoor vs Outdoor**: Compare to outside AQI

### Sleep & Comfort (7 sensors)
- **Sleep Environment Score**: Predicts sleep quality (temp + CO2)
- **Window Status**: Infers if bedroom window is open
- **Ventilation Effectiveness**: Whole-house air circulation
- **Comfort Index**: Overall comfort metric

---

## 🐛 Troubleshooting

### "Template sensors not loading"

**Cause**: Directory path wrong or YAML syntax error

**Fix**:
1. Verify `configuration-template-addons/` directory exists in same folder as configuration.yaml
2. Check logs: Settings → System → Logs → Search for "template"
3. Verify YAML syntax in each file (indentation, colons)

### "Integration platform not found"

**Cause**: `sensor:` section syntax error

**Fix**:
```yaml
# Wrong (missing colon):
sensor
  - platform: integration

# Right:
sensor:
  - platform: integration
```

### "Energy sensors showing unavailable"

**Cause**: Need to wait for data accumulation

**Fix**:
1. Wait 2+ hours after restart
2. Check power sensors updating: `sensor.basement_heat_pump_outdoor_power`
3. Verify values are changing (not stuck at 0)

### "Outdoor power estimates are wrong"

**Cause**: Heat pump size differs from default (2.5 ton assumed)

**Fix**: Edit `configuration-template-addons/02_hvac_outdoor_units.yaml`:

```yaml
{% if compressor_state == 'stage2' %}
  {% set base_power = 6500 %}  # Adjust for your unit size
{% elif compressor_state == 'stage1' %}
  {% set base_power = 4500 %}  # Adjust for your unit size
```

**Heat pump size guide:**
- 2 ton: `3500` (stage1), `5500` (stage2)
- 2.5 ton: `4500` (stage1), `6500` (stage2) ← Current default
- 3 ton: `5500` (stage1), `7500` (stage2)

### "Duplicate sensor unique_id"

**Cause**: Old sensor definitions still in configuration.yaml

**Fix**: Remove old manual sensor definitions before using directory method

---

## 🧹 Cleanup (After Verification)

Once everything is working for 24+ hours, you can delete these old files:

```bash
# Old YAML files (no longer needed):
rm comprehensive_template_sensors.yaml
rm merged_template_sensors.yaml
rm old_sensors.yaml
rm heat_pump_outdoor_energy_estimate.yaml
rm energy_dashboard_simple.yaml
rm energy_dashboard_sensors.yaml
rm FINAL_ALL_SENSORS.yaml
```

**Keep these:**
- ✅ `configuration-template-addons/` (directory with all sensors)
- ✅ `CONFIGURATION_YAML_ADDITIONS.yaml` (reference)
- ✅ `INSTALLATION_GUIDE.md` (this file)
- ✅ `SENSOR_MERGE_REVIEW.md` (documentation)
- ✅ `home_assistant_automations.yaml` (alerts)

---

## 📈 BigQuery Export

All sensors automatically export to BigQuery via your existing integration.

### Query Example: Daily HVAC Energy (Indoor + Outdoor)

```sql
WITH daily_hvac AS (
  SELECT
    DATE(last_changed) as date,
    entity_id,
    MAX(SAFE_CAST(state AS FLOAT64)) - MIN(SAFE_CAST(state AS FLOAT64)) as daily_kwh
  FROM `ha_data.sensor_data`
  WHERE entity_id IN (
    'sensor.furnace_basement_energy',
    'sensor.shelly_attic_hvac_energy',
    'sensor.basement_heat_pump_outdoor_energy',
    'sensor.upstairs_heat_pump_outdoor_energy'
  )
  AND DATE(last_changed) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  GROUP BY date, entity_id
)
SELECT
  date,
  SUM(CASE WHEN entity_id = 'sensor.furnace_basement_energy'
           THEN daily_kwh ELSE 0 END) as basement_indoor_kwh,
  SUM(CASE WHEN entity_id LIKE '%basement%outdoor%'
           THEN daily_kwh ELSE 0 END) as basement_outdoor_kwh,
  SUM(CASE WHEN entity_id = 'sensor.shelly_attic_hvac_energy'
           THEN daily_kwh ELSE 0 END) as upstairs_indoor_kwh,
  SUM(CASE WHEN entity_id LIKE '%upstairs%outdoor%'
           THEN daily_kwh ELSE 0 END) as upstairs_outdoor_kwh
FROM daily_hvac
GROUP BY date
ORDER BY date DESC
```

---

## 🎯 Next Steps

1. ✅ Complete installation (Steps 1-3 above)
2. ⏳ Wait 2 hours for energy sensors
3. ✅ Add to Energy dashboard
4. ⏳ Wait 1 week for data accumulation
5. 📊 Analyze fan mode impact on CO2 (BigQuery)
6. 📊 Compare indoor vs outdoor HVAC energy
7. 📊 Correlate sleep score with environment sensors
8. ⚙️ Optimize HVAC settings based on data

---

## 📞 Support

If you encounter issues:

1. Check this guide's troubleshooting section
2. Review `configuration-template-addons/README.md` for detailed docs
3. Check Home Assistant logs: Settings → System → Logs
4. Verify entity names match your system (may need adjustments)

---

**Last Updated:** 2025-11-09
**Files Created:** 6 YAML sensor files + 3 documentation files
**Total Sensors:** 49 template + 2 integration = 51 sensors (+ 4 optional utility meters)
