# BigQuery Export - Quick Start Guide 🚀

## Installation

### Via HACS (Recommended)
1. HACS → Integrations → ⋮ → Custom repositories
2. Add: `https://github.com/tbailey1712/ha-bigquery-export`
3. Category: Integration
4. Install → Restart Home Assistant

### Manual
1. Copy `custom_components/bigquery_export` to your HA config
2. Restart Home Assistant

## Initial Setup

### 1. Get Google Cloud Credentials
```bash
# In Google Cloud Console:
1. Create project
2. Enable BigQuery API
3. Create service account
4. Download JSON key
```

### 2. Configure Integration
1. Settings → Devices & Services → Add Integration
2. Search "BigQuery Export"
3. Upload service account JSON
4. Enter project ID and dataset ID
5. Complete setup

## First Export

### Test Export (Last 7 Days)
```yaml
service: bigquery_export.manual_export
data:
  days_back: 7
```

### Check Your Data
```sql
-- In BigQuery Console
SELECT
  DATE(last_changed) as date,
  COUNT(*) as records
FROM `project.dataset.sensor_data`
WHERE record_type = 'state'
GROUP BY date
ORDER BY date DESC
LIMIT 10
```

## Database Analysis Workflow

### Step 1: Check Local Retention
```yaml
service: bigquery_export.check_database_retention
```
**Result:** Creates sensors showing your local database stats

### Step 2: Analyze Coverage
```yaml
service: bigquery_export.analyze_export_status
```
**Result:** Shows what % of your data is in BigQuery

### Step 3: Find Gaps
```yaml
service: bigquery_export.find_data_gaps
```
**Result:** Lists missing date ranges

### Step 4: Estimate Backfill
```yaml
service: bigquery_export.estimate_backfill
data:
  start_date: "2025-01-01"
  end_date: "2025-03-15"
```
**Result:** Shows cost and time estimates

### Step 5: Run Backfill
```yaml
service: bigquery_export.manual_export
data:
  start_time: "2025-01-01T00:00:00"
  end_time: "2025-01-07T23:59:59"
  use_bulk_upload: true
```
**Result:** Exports the gap (repeat for each week)

## Dashboard Card Example

```yaml
type: entities
title: BigQuery Export Status
entities:
  - entity: sensor.bigquery_export_status
    name: Export Status
  - entity: sensor.local_database_retention
    name: Local Data
  - entity: sensor.bigquery_export_coverage
    name: Coverage
  - entity: sensor.bigquery_data_gaps
    name: Data Gaps
  - type: button
    name: Check Database
    tap_action:
      action: call-service
      service: bigquery_export.check_database_retention
  - type: button
    name: Analyze Coverage
    tap_action:
      action: call-service
      service: bigquery_export.analyze_export_status
```

## Automation Example

### Daily Incremental Export
```yaml
automation:
  - alias: "BigQuery Daily Export"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: bigquery_export.incremental_export
```

### Weekly Full Analysis
```yaml
automation:
  - alias: "BigQuery Weekly Analysis"
    trigger:
      - platform: time
        at: "06:00:00"
      - platform: time
        day_of_week: mon
    action:
      - service: bigquery_export.analyze_export_status
      - service: bigquery_export.find_data_gaps
      - condition: state
        entity_id: sensor.bigquery_data_gaps
        state: "0"
        state_not: true
      - service: notify.persistent_notification
        data:
          message: "⚠️ BigQuery has {{ states('sensor.bigquery_data_gaps') }} data gaps. Check notifications."
          title: "Data Gaps Detected"
```

## Common Queries

### Energy Usage by Day
```sql
SELECT
  DATE(last_changed) as date,
  AVG(CAST(state AS FLOAT64)) as avg_kwh
FROM `project.dataset.sensor_data`
WHERE entity_id = 'sensor.total_energy'
  AND record_type = 'state'
  AND state NOT IN ('unknown', 'unavailable')
GROUP BY date
ORDER BY date DESC
```

### Device On-Time Analysis
```sql
SELECT
  friendly_name,
  COUNT(*) as state_changes,
  COUNTIF(state = 'on') as on_count,
  ROUND(COUNTIF(state = 'on') / COUNT(*) * 100, 1) as on_percent
FROM `project.dataset.sensor_data`
WHERE domain = 'switch'
  AND record_type = 'state'
  AND DATE(last_changed) >= CURRENT_DATE() - 30
GROUP BY friendly_name
ORDER BY on_percent DESC
```

### Find Most Active Sensors
```sql
SELECT
  entity_id,
  friendly_name,
  COUNT(*) as updates,
  COUNT(DISTINCT DATE(last_changed)) as active_days
FROM `project.dataset.sensor_data`
WHERE record_type = 'state'
  AND DATE(last_changed) >= CURRENT_DATE() - 7
GROUP BY entity_id, friendly_name
ORDER BY updates DESC
LIMIT 20
```

## Troubleshooting

### Export Failing
1. Check logs: Settings → System → Logs
2. Search for "bigquery_export"
3. Verify service account has BigQuery Data Editor role
4. Check disk space (bulk exports need temp storage)

### Sensors Not Updating
1. Run service calls manually
2. Check entity attributes for errors
3. Verify recorder database is accessible
4. Restart integration: Settings → Devices & Services

### High Costs
1. Check partitioning: Should be by `last_changed`
2. Add clustering: `entity_id`, `domain`
3. Review query patterns: Use date filters
4. Consider reducing retention in BigQuery

## Best Practices

### Export Strategy
- ✅ Daily incremental exports (automated)
- ✅ Weekly full analysis (to catch gaps)
- ✅ Monthly backfill check (before purge)
- ❌ Don't export every minute (expensive)

### Data Management
- ✅ Use entity filtering for noisy sensors
- ✅ Archive data before reducing recorder retention
- ✅ Monitor BigQuery storage costs
- ❌ Don't backfill if not needed

### Query Optimization
- ✅ Always filter by date (uses partitioning)
- ✅ Filter by entity_id early (uses clustering)
- ✅ Use record_type = 'state' for sensor data
- ❌ Don't scan full table without WHERE clause

## Support

- **Documentation:** [GitHub README](https://github.com/tbailey1712/ha-bigquery-export)
- **Issues:** [GitHub Issues](https://github.com/tbailey1712/ha-bigquery-export/issues)
- **Discussions:** [GitHub Discussions](https://github.com/tbailey1712/ha-bigquery-export/discussions)

## Next Steps

1. ✅ Complete initial export
2. ✅ Run database analysis services
3. ✅ Set up daily automation
4. ✅ Create dashboard card
5. 🎯 Build custom queries for your use case
6. 🎯 Set up Data Studio dashboards
7. 🎯 Explore ML/AI analysis options

---

**Version:** 1.2.0
**Last Updated:** 2025-11-28
