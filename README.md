# Home Assistant BigQuery Export Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/tbailey/ha-bigquery-export.svg)](https://github.com/tbailey/ha-bigquery-export/releases)
[![License](https://img.shields.io/github/license/tbailey/ha-bigquery-export.svg)](LICENSE)

I had been wanting to be able to analyze more than the 90 days of data that recorder keeps in the local SQL database.  With this plugin, you can export your Home Assistant sensor data to Google BigQuery for long-term storage, analytics, and AI/ML analysis. It defaults to a sensor_data table and brings along all of the attributes.  

If you have really noisy sensors or ones that don't make sense to keep long term (like daily packet counts on your network), you can also filter them out.

Built for enterprise-grade data workflows with automatic deduplication, bulk upload capabilities, and comprehensive monitoring.

## 🎯 Key Features

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

### 4. BigQuery Schema
The integration automatically creates an optimized table with this schema:

```sql
CREATE TABLE `your-project.ha_data.sensor_data` (
  entity_id STRING NOT NULL,
  state STRING,
  attributes STRING,  -- JSON as string for flexibility
  last_changed TIMESTAMP NOT NULL,
  last_updated TIMESTAMP NOT NULL,
  context_id STRING,
  context_user_id STRING,
  domain STRING,
  friendly_name STRING,
  unit_of_measurement STRING,
  export_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(last_changed)
CLUSTER BY entity_id, domain;
```

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
- [GitHub Issues](https://github.com/yourusername/ha-bigquery-export/issues)
- [Home Assistant Community](https://community.home-assistant.io/)

## Changelog

### v1.0.0
- Initial release
- Basic BigQuery export functionality
- Scheduled and manual exports
- Configuration UI
- Status monitoring sensor