# Home Assistant BigQuery Export Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/tbailey1712/ha-bigquery-export.svg)](https://github.com/tbailey1712/ha-bigquery-export/releases)
[![License](https://img.shields.io/github/license/tbailey1712/ha-bigquery-export.svg)](LICENSE)

I had been wanting to be able to analyze more than the 90 days of data that recorder keeps in the local SQL database.  With this plugin, you can export your Home Assistant sensor data to Google BigQuery for long-term storage, analytics, and AI/ML analysis. It defaults to a sensor_data table and brings along all of the attributes.  

If you have really noisy sensors or ones that don't make sense to keep long term (like daily packet counts on your network), you can also filter them out.

Built for enterprise-grade data workflows with automatic deduplication, bulk upload capabilities, and comprehensive monitoring.

## 🎯 Key Features

### 🔍 **Database Analysis & Diagnostics** ✨ NEW
- **Local Database Inspection**: Check your recorder retention and available data
- **Export Coverage Analysis**: Compare local DB vs BigQuery to identify gaps
- **Gap Detection**: Find missing date ranges automatically
- **Backfill Cost Estimation**: Calculate time, size, and costs before exporting
- **Visual Sensors**: See retention, coverage %, and gaps on your dashboard

### 📊 **Smart Data Export**
- **Bulk Upload for Large Datasets**: Automatically switches to file-based bulk upload for datasets >10K records
- **Intelligent Chunking**: Handles massive historical exports (90+ days) via optimized 7-day chunks
- **Real-time Progress Tracking**: Live status updates during long-running exports
- **Automatic Deduplication**: Prevents duplicate data with smart MERGE operations

### 🔒 **Enterprise Security**
- **Google Service Account Authentication**: Secure OAuth2 with minimal IAM permissions
- **Credential Protection**: Service account keys stored securely in Home Assistant
- **Audit Logging**: Comprehensive export tracking and error reporting

### 🚀 **Production Ready**
- **Database Compatibility**: Works with SQLite, MariaDB, PostgreSQL
- **Modern HA Schema Support**: Full compatibility with Home Assistant's normalized database
- **Error Recovery**: Robust error handling with automatic cleanup
- **Resource Management**: Disk space checking and memory optimization

### 📈 **Monitoring & Analytics**
- **Export Statistics**: Track records exported, timing, and success rates
- **BigQuery Optimization**: Partitioned tables, clustered indexing, optimized schemas
- **Home Assistant Integration**: Native sensor entity with real-time status

## 🏗️ Architecture

```
Home Assistant → Recorder DB → Export Service → BigQuery → AI/ML Analysis
     ↓              ↓              ↓              ↓
   Entities    MariaDB/SQLite   Bulk Upload   Analytics
```

**Data Flow:**
1. **Source**: Home Assistant Recorder database (states, entities, attributes)
2. **Processing**: Intelligent export engine with chunking and deduplication
3. **Transport**: JSONL bulk upload or streaming insert based on dataset size
4. **Destination**: BigQuery with time-partitioned, clustered tables
5. **Analytics**: Ready for Data Studio, ML models, long-term analysis

## 📦 Installation

### Via HACS (Recommended)
1. Open HACS in Home Assistant
2. Go to Integrations
3. Click the 3-dot menu → Custom Repositories
4. Add: `https://github.com/tbailey1712/ha-bigquery-export`
5. Category: Integration
6. Install "BigQuery Export"
7. Restart Home Assistant

### Manual Installation
1. Download the latest release
2. Extract to `custom_components/bigquery_export/`
3. Restart Home Assistant

## ⚙️ Configuration

### 1. Google Cloud Setup
```bash
# Create a BigQuery dataset
bq mk --location=US your-project:ha_data

# Create service account with minimal permissions
gcloud iam service-accounts create ha-bigquery-export \
  --display-name="Home Assistant BigQuery Export"

# Grant BigQuery Data Editor role
gcloud projects add-iam-policy-binding your-project \
  --member="serviceAccount:ha-bigquery-export@your-project.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

# Create and download key
gcloud iam service-accounts keys create ha-bigquery-key.json \
  --iam-account=ha-bigquery-export@your-project.iam.gserviceaccount.com
```

### 2. Secure Credential Storage (Recommended)

For security, store your service account key in `secrets.yaml`:

```yaml
# secrets.yaml (in your Home Assistant config directory)
bigquery_service_account: |
  {
    "type": "service_account",
    "project_id": "your-project-123",
    "private_key_id": "abc123def456...",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANotARealKeyHereSjAgEAAoIBAQC7...\n-----END PRIVATE KEY-----\n",
    "client_email": "ha-bigquery-export@your-project-123.iam.gserviceaccount.com",
    "client_id": "123456789012345678901",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/ha-bigquery-export%40your-project-123.iam.gserviceaccount.com"
  }
```

### 3. Home Assistant Integration
1. Go to Settings → Devices & Services → Add Integration
2. Search for "BigQuery Export"
3. Enter your configuration:
   - **Project ID**: Your Google Cloud project
   - **Dataset ID**: `ha_data` (or your chosen dataset)
   - **Service Account Key**: `!secret bigquery_service_account`

**⚠️ Security Note**: While you can paste the JSON directly, using `!secret` references is strongly recommended to keep credentials secure.

### 4. BigQuery Schema - Unified Timeline Model
The integration uses a unified timeline model that stores both state changes and events in a single table:

```sql
CREATE TABLE `your-project.ha_data.sensor_data` (
  -- Core identity (unified timeline)
  record_id STRING,  -- Unique ID: event_<id>_<ts> or state record
  timestamp TIMESTAMP,  -- Unified timestamp field
  record_type STRING,  -- 'state' or 'event'

  -- Entity info (applies to all records)
  entity_id STRING NOT NULL,
  domain STRING,

  -- State-specific fields (NULL for events)
  state STRING,
  attributes STRING,  -- JSON as string (state attributes)
  last_changed TIMESTAMP,
  last_updated TIMESTAMP,

  -- Event-specific fields (NULL for states)
  event_type STRING,  -- automation_triggered, script_started, etc.
  event_data STRING,  -- JSON event data
  triggered_by STRING,  -- What triggered the event

  -- Context linking (same for both states and events)
  context_id STRING,
  context_user_id STRING,

  -- Metadata from entity registry
  friendly_name STRING,
  unit_of_measurement STRING,
  area_id STRING,  -- Area ID from entity registry
  area_name STRING,  -- Human-readable area name
  labels ARRAY<STRING>,  -- Array of label names from entity registry

  -- Pre-computed time-based features for ML
  hour_of_day INTEGER,
  day_of_week INTEGER,  -- 0=Monday, 6=Sunday
  is_weekend BOOLEAN,
  is_night BOOLEAN,  -- True if hour < 6 or hour >= 21
  time_of_day STRING,  -- morning, afternoon, evening, night
  month INTEGER,
  season STRING,  -- winter, spring, summer, fall
  state_changed BOOLEAN,  -- True if state actually changed vs attribute update

  export_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(COALESCE(last_changed, timestamp))
CLUSTER BY entity_id, domain, record_type;
```

**New in v1.2.0**:
- **Unified Timeline Model**: State changes and events (automations, scripts, scenes) in one table
- **Pre-computed ML Features**: Time-based features calculated at export time for efficient queries
- **Event Export**: Capture automation triggers, script starts, and scene activations alongside state changes
- **Context Linking**: Connect events to state changes via `context_id` for cause-and-effect analysis

**New in v1.1.0**: Area and label information is now automatically included with each export, allowing you to filter and analyze by room/location and custom labels.

**Smart Inheritance**: If an entity doesn't have explicit labels/areas assigned, the integration automatically falls back to the parent device's labels/areas. This means if you assign labels and an area to a device (e.g., "Awair Family Room"), all its child sensor entities will inherit those labels and areas in the export!

**Backfill Support**: Re-exporting the same time range will automatically update existing records with the latest label/area information. This is perfect for backfilling metadata after you've organized your entities with labels and areas.

## 🚀 Usage

### Manual Export
Export specific time ranges using Home Assistant services:

```yaml
# Export last 7 days (recommended chunk size)
service: bigquery_export.manual_export
data:
  days_back: 7

# Export specific date range  
service: bigquery_export.manual_export
data:
  start_time: "2025-01-01T00:00:00"
  end_time: "2025-01-08T00:00:00"

# Export last 90 days (will auto-chunk into 7-day batches)
service: bigquery_export.manual_export
data:
  days_back: 90
```

### Historical Backfill (New Users)
For first-time setup with lots of historical data:

```yaml
# Start with recent data (fast)
- service: bigquery_export.manual_export
  data:
    days_back: 7

# Then backfill in chunks (recommended approach)
- service: bigquery_export.manual_export
  data:
    start_time: "2025-06-26T00:00:00"
    end_time: "2025-07-03T00:00:00"

# Continue with earlier periods...
```

### **Backfilling Labels/Areas (v1.1.0+)**
After upgrading to v1.1.0 and organizing your entities with labels/areas, backfill the metadata:

```yaml
# Re-export recent data to update with labels/areas
service: bigquery_export.manual_export
data:
  days_back: 90  # Or however far back you want to update

# For older data, export in chunks
service: bigquery_export.manual_export
data:
  start_time: "2025-01-01T00:00:00"
  end_time: "2025-01-08T00:00:00"
```

**How it works**: The MERGE operation now includes `WHEN MATCHED` logic that updates `area_id`, `area_name`, and `labels` columns on existing records. This means:
- ✅ New records get full metadata
- ✅ Existing records get metadata updated
- ✅ No duplicate rows created
- ✅ State/timestamp data remains unchanged

**Schema Migration**: The integration automatically adds the new columns (`area_id`, `area_name`, `labels`) to your existing table on first run. You'll see a log message: `Adding 3 new columns to table: ['area_id', 'area_name', 'labels']`

### Monitoring
Track export progress with the built-in sensor:

```yaml
# In your dashboard
type: entities
entities:
  - entity: sensor.bigquery_export_status
    name: BigQuery Export
```

**Sensor Attributes:**
- `export_status`: Connection status (connected/disconnected)
- `last_export`: Timestamp of last successful export
- `records_exported`: Number of records in last export
- `current_status`: Real-time export progress
- `project_id`, `dataset_id`, `table_id`: Configuration details

## 🎛️ Advanced Configuration

### Export Performance Tuning
```python
# In const.py - customize for your system
DEFAULT_BATCH_SIZE = 1000          # Records per batch for small exports
BULK_UPLOAD_THRESHOLD = 10000      # Switch to bulk upload above this size
MAX_EXPORT_DAYS = 90              # Maximum days per export request
```

### Database Optimization
```yaml
# For large HA instances, consider MariaDB
recorder:
  db_url: mysql://user:pass@host/homeassistant
  auto_purge: true
  purge_keep_days: 90
```

### BigQuery Cost Optimization
```sql
-- Query recent data efficiently
SELECT *
FROM `your-project.ha_data.sensor_data`
WHERE DATE(last_changed) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
  AND entity_id LIKE 'sensor.%'

-- Aggregate for analytics (uses clustering)
SELECT 
  entity_id,
  DATE(last_changed) as date,
  COUNT(*) as measurements,
  AVG(SAFE_CAST(state AS FLOAT64)) as avg_value
FROM `your-project.ha_data.sensor_data`
WHERE domain = 'sensor'
  AND DATE(last_changed) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY entity_id, date
ORDER BY entity_id, date
```

## 🔧 Technical Details

### Export Strategies
The integration automatically chooses the optimal export method:

1. **Batch Processing** (< 10K records):
   - Processes in chunks of 1,000 records
   - Uses streaming insert API
   - Real-time progress updates
   - ~45 seconds for 7 days (2.2M records)

2. **Bulk File Upload** (> 10K records):
   - Creates temporary JSONL file
   - Single BigQuery load job
   - Disk space validation
   - Automatic cleanup
   - ~2-3 minutes for 30+ days

### Database Compatibility
Works with all Home Assistant recorder configurations:

- **SQLite** (default): Direct file access
- **MariaDB/MySQL**: Optimized for large datasets  
- **PostgreSQL**: Full feature support
- **External Databases**: Network-based queries

### Data Deduplication
Prevents duplicate data with sophisticated MERGE operations:

```sql
MERGE target_table AS target
USING source_data AS source
ON target.entity_id = source.entity_id 
   AND target.last_changed = source.last_changed
WHEN NOT MATCHED THEN INSERT (...)
```

### Resource Management
- **Disk Space Checking**: Validates 2x estimated file size before export
- **Memory Optimization**: Streams large result sets
- **Connection Pooling**: Efficient database access
- **Automatic Cleanup**: Removes temporary files and tables

## Example Queries

### Daily sensor averages
```sql
SELECT
  DATE(last_changed) as date,
  entity_id,
  AVG(CAST(state AS FLOAT64)) as avg_value
FROM `project.dataset.sensor_data`
WHERE domain = 'sensor'
  AND state NOT IN ('unavailable', 'unknown')
  AND SAFE_CAST(state AS FLOAT64) IS NOT NULL
GROUP BY 1, 2
ORDER BY 1 DESC, 2;
```

### Entity activity over time
```sql
SELECT
  entity_id,
  COUNT(*) as state_changes,
  MIN(last_changed) as first_seen,
  MAX(last_changed) as last_seen
FROM `project.dataset.sensor_data`
WHERE DATE(last_changed) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY entity_id
ORDER BY state_changes DESC;
```

### **NEW: Query by Area**
```sql
-- Average temperature by room/area
SELECT
  area_name,
  AVG(SAFE_CAST(state AS FLOAT64)) as avg_temp,
  COUNT(*) as measurements
FROM `project.dataset.sensor_data`
WHERE domain = 'sensor'
  AND entity_id LIKE '%temperature%'
  AND area_name IS NOT NULL
  AND DATE(last_changed) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY area_name
ORDER BY avg_temp DESC;
```

### **NEW: Query by Label**
```sql
-- Find all entities with a specific label
SELECT DISTINCT
  entity_id,
  friendly_name,
  domain,
  area_name
FROM `project.dataset.sensor_data`
WHERE 'HVAC' IN UNNEST(labels)  -- Replace 'HVAC' with your label name
  AND DATE(last_changed) >= CURRENT_DATE()
ORDER BY entity_id;
```

### **NEW: Multi-label Analysis**
```sql
-- Analyze entities with multiple labels (e.g., "Important" AND "Energy")
SELECT
  entity_id,
  area_name,
  labels,
  COUNT(*) as state_changes,
  APPROX_QUANTILES(SAFE_CAST(state AS FLOAT64), 4)[OFFSET(2)] as median_value
FROM `project.dataset.sensor_data`
WHERE 'Important' IN UNNEST(labels)
  AND 'Energy' IN UNNEST(labels)
  AND DATE(last_changed) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY entity_id, area_name, labels
ORDER BY state_changes DESC;
```

### **NEW v1.2.0: Event Analysis**
```sql
-- See all automation triggers from last 7 days
SELECT
  entity_id,
  friendly_name,
  timestamp,
  triggered_by,
  area_name
FROM `project.dataset.sensor_data`
WHERE record_type = 'event'
  AND event_type = 'automation_triggered'
  AND DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
ORDER BY timestamp DESC;
```

### **NEW v1.2.0: Cause and Effect Analysis**
```sql
-- Find state changes caused by automation triggers using context linking
SELECT
  e.timestamp as trigger_time,
  e.entity_id as automation,
  e.friendly_name as automation_name,
  s.entity_id as affected_entity,
  s.state as new_state,
  s.last_changed as state_change_time,
  TIMESTAMP_DIFF(s.last_changed, e.timestamp, SECOND) as delay_seconds
FROM `project.dataset.sensor_data` e
JOIN `project.dataset.sensor_data` s
  ON e.context_id = s.context_id
WHERE e.record_type = 'event'
  AND e.event_type = 'automation_triggered'
  AND s.record_type = 'state'
  AND DATE(e.timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
ORDER BY e.timestamp DESC, delay_seconds ASC
LIMIT 100;
```

### **NEW v1.2.0: Time-Based Pattern Analysis**
```sql
-- Analyze automation triggers by time of day and day of week
SELECT
  entity_id,
  time_of_day,
  CASE day_of_week
    WHEN 0 THEN 'Monday'
    WHEN 1 THEN 'Tuesday'
    WHEN 2 THEN 'Wednesday'
    WHEN 3 THEN 'Thursday'
    WHEN 4 THEN 'Friday'
    WHEN 5 THEN 'Saturday'
    WHEN 6 THEN 'Sunday'
  END as day_name,
  COUNT(*) as trigger_count
FROM `project.dataset.sensor_data`
WHERE record_type = 'event'
  AND event_type = 'automation_triggered'
  AND DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY entity_id, time_of_day, day_of_week
ORDER BY entity_id, day_of_week, time_of_day;
```

### **NEW v1.2.0: Unified Timeline View**
```sql
-- View both state changes and events in chronological order
SELECT
  COALESCE(timestamp, last_changed) as event_time,
  record_type,
  entity_id,
  CASE
    WHEN record_type = 'state' THEN CONCAT('State: ', state)
    WHEN record_type = 'event' THEN CONCAT('Event: ', event_type)
  END as description,
  area_name,
  context_id
FROM `project.dataset.sensor_data`
WHERE entity_id IN ('automation.morning_routine', 'light.bedroom')
  AND DATE(COALESCE(timestamp, last_changed)) = CURRENT_DATE()
ORDER BY event_time DESC;
```

## Troubleshooting

### Common Issues

1. **Authentication Error**: Check your service account key format and permissions
2. **Dataset Not Found**: Ensure your service account has dataset creation permissions
3. **Export Failures**: Check Home Assistant logs for detailed error messages
4. **Performance Issues**: Consider adjusting export schedule for large datasets

### Debugging

Enable debug logging in Home Assistant:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.bigquery_export: debug
```

## Security Considerations

### **Credential Security**
- **🔒 Use `!secret` references**: Store service account keys in `secrets.yaml`, not in configuration UI
- **🔑 Minimal permissions**: Grant only `BigQuery Data Editor` and `BigQuery Job User` roles
- **🔄 Key rotation**: Regularly rotate service account keys for enhanced security
- **📁 File permissions**: Ensure `secrets.yaml` has restricted file permissions (600)

### **Data Protection**
- **🚀 Encrypted transmission**: All data sent to BigQuery via HTTPS/TLS
- **🎯 Selective export**: Configure entity filtering to export only necessary sensors
- **🚫 No credential logging**: Service account keys are never logged in Home Assistant
- **🔒 BigQuery IAM**: Use BigQuery IAM policies to control data access

### **Network Security**
- **🌐 Cloud endpoints**: Connections made directly to Google Cloud APIs
- **🔐 OAuth 2.0**: Secure authentication using Google's OAuth 2.0 implementation
- **📊 Audit logs**: Enable Google Cloud audit logging for access tracking

## Performance

- Optimized batch processing (1000 records/batch)
- Partitioned tables for efficient querying
- Clustered storage for better performance
- Asynchronous execution to avoid blocking Home Assistant

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
- [GitHub Issues](https://github.com/tbailey1712/ha-bigquery-export/issues)
- [Home Assistant Community](https://community.home-assistant.io/)

## Changelog

### v1.0.0
- Initial release
- Basic BigQuery export functionality
- Scheduled and manual exports
- Configuration UI
- Status monitoring sensor