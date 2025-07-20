"""Constants for BigQuery Export integration."""

DOMAIN = "bigquery_export"

# Configuration keys
CONF_PROJECT_ID = "project_id"
CONF_DATASET_ID = "dataset_id"
CONF_TABLE_ID = "table_id"
CONF_SERVICE_ACCOUNT_KEY = "service_account_key"
CONF_EXPORT_SCHEDULE = "export_schedule"
CONF_ENTITIES = "entities"
CONF_ALLOWED_ENTITIES = "allowed_entities"
CONF_DENIED_ATTRIBUTES = "denied_attributes"
CONF_FILTERING_MODE = "filtering_mode"

# Filtering modes
FILTERING_MODE_EXCLUDE = "exclude"  # Export all with exclusions (legacy behavior)
FILTERING_MODE_INCLUDE = "include"  # Export only explicitly allowed entities
CONF_LAST_EXPORT_TIME = "last_export_time"

# Default values
DEFAULT_EXPORT_SCHEDULE = "weekly"
DEFAULT_BATCH_SIZE = 1000
DEFAULT_TABLE_ID = "sensor_data"

# Export schedule options
EXPORT_SCHEDULES = {
    "hourly": 1,
    "daily": 24,
    "weekly": 168,
    "monthly": 720,
}

# BigQuery schema fields
BIGQUERY_SCHEMA = [
    {"name": "entity_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "state", "type": "STRING", "mode": "NULLABLE"},
    {"name": "attributes", "type": "STRING", "mode": "NULLABLE"},
    {"name": "last_changed", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "last_updated", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "context_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "context_user_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "domain", "type": "STRING", "mode": "NULLABLE"},
    {"name": "friendly_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "unit_of_measurement", "type": "STRING", "mode": "NULLABLE"},
    {"name": "export_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
]

# Service names
SERVICE_MANUAL_EXPORT = "manual_export"
SERVICE_INCREMENTAL_EXPORT = "incremental_export"

# Attributes
ATTR_EXPORT_STATUS = "export_status"
ATTR_LAST_EXPORT = "last_export"
ATTR_RECORDS_EXPORTED = "records_exported"
ATTR_NEXT_EXPORT = "next_export"

# Default entity filtering for data quality (user can override)
# Priority sensors to always include (examples - users should configure their own)
DEFAULT_PRIORITY_SENSORS = [
    # HVAC & Climate examples
    'climate.*',
    'sensor.*temperature*',
    'sensor.*energy*',
    'sensor.*power*',
    
    # Weather examples  
    'weather.*',
    
    # Network essentials
    'sensor.*download_speed',
    'sensor.*upload_speed',
    'sensor.speedtest*',
]

# Network sensors to include (selective list)
NETWORK_SENSORS_TO_KEEP = {
    'sensor.total_lan_1h_average',
    'sensor.wan_download_speed',
    'sensor.wan_upload_speed', 
    'sensor.total_wan_usage',
    'sensor.wan_download_utilization',
    'sensor.wan_upload_utilization',
    'sensor.speedtest_download',
    'sensor.speedtest_upload'
}

# NETWORK NOISE TO ELIMINATE - Aggressive filtering
EXCLUDE_NETWORK_PATTERNS = [
    'sensor.firewall_interface_',         # All interface-level data (was 54k+ records each!)
    'sensor.firewall_gateway_',           # Gateway ping/delay sensors
    '_packets_per_second',                # Packet-level granularity (too detailed)
    '_kilobytes_per_second',             # Per-second bandwidth (too frequent)
    '_inbytes_',                         # Individual interface byte counters
    '_outbytes_',                        # Individual interface byte counters  
    '_inpkts_',                          # Individual interface packet counters
    '_outpkts_',                         # Individual interface packet counters
    '_stddev',                           # Network standard deviation sensors
    '_delay',                            # Network delay/ping sensors
    'sensor.total_internal_inbound_traffic',   # Internal traffic counters
    'sensor.total_internal_outbound_traffic',  # Internal traffic counters
    # Legacy network noise patterns
    'sensor.home_network_speed',
    'sensor.camera_network_speed', 
    'sensor.iot_network_speed',
    'sensor.dmz_network_speed',
    'sensor.guest_network_speed',
    'sensor.port_',  # All port sensors
    'sensor.total_internal_',  # Internal traffic sensors
    '_peak_mbps',  # Peak sensors update too frequently
    '_utilization',  # Most utilization sensors (except WAN)
    '_network_speed',  # Any remaining network speed sensors
    '_lan_',  # LAN traffic sensors
    '_traffic_',  # Traffic sensors
    '_bandwidth_',  # Bandwidth sensors
    'sensor.unifi_',  # UniFi network sensors (if you have them)
    'sensor.pfsense_',  # pfSense sensors (except essential ones)
]

# EXCLUDE BY UNITS (Network-specific)
EXCLUDE_NETWORK_UNITS = [
    'packets/s',                         # Packet rate data
    'kB/s',                             # Per-second bandwidth
    'MB/s',                             # Per-second bandwidth  
    'ms',                               # Network latency
]

# ESSENTIAL NETWORK DATA TO KEEP
KEEP_NETWORK_ESSENTIALS = {
    'sensor.connected_clients',          # How many devices connected
    'sensor.firewall_cpu_usage',        # System health
    'sensor.firewall_system_load_average_one_minute',  # System performance
    # Keep any daily/hourly summaries if they exist
    'sensor.wan_download_daily',         # Daily totals (if you have them)
    'sensor.wan_upload_daily',           # Daily totals 
    'sensor.wan_download_monthly',       # Monthly totals
    'sensor.wan_upload_monthly',         # Monthly totals
    # Keep any speed test results
    'sensor.speedtest_download',         # ISP performance monitoring
    'sensor.speedtest_upload',           # ISP performance monitoring
}

# OTHER PATTERNS TO EXCLUDE
EXCLUDE_OTHER_PATTERNS = [
    # AGGRESSIVE GROW TENT FILTERING - Kill the voltage/current spam
    'sensor.grow_tent_voltage',           # Kill the voltage spam
    'sensor.grow_tent_current',           # Kill the current spam  
    'sensor.grow_tent_current_consumption', # Kill current consumption spam
]

# Keep only essential grow tent data
GROW_TENT_ESSENTIALS = {
    'sensor.grow_tent_today_s_consumption',    # Daily totals only
    'sensor.grow_tent_this_month_s_consumption', # Monthly totals only
}