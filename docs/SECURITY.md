# Security Guidelines for BigQuery Export Integration

## Overview
This document outlines the security hardening measures implemented in the BigQuery Export integration and provides guidance for secure deployment.

## IAM Permissions (Principle of Least Privilege)

### Required BigQuery Permissions
The service account should have **minimal permissions** for secure operation:

```json
{
  "bindings": [
    {
      "role": "roles/bigquery.dataEditor",
      "members": ["serviceAccount:your-service-account@project.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/bigquery.jobUser", 
      "members": ["serviceAccount:your-service-account@project.iam.gserviceaccount.com"]
    }
  ]
}
```

### Specific Permissions Breakdown
- `bigquery.datasets.get` - Read dataset metadata
- `bigquery.tables.get` - Read table schema
- `bigquery.tables.updateData` - Insert/update data
- `bigquery.jobs.create` - Run queries and load jobs

### What NOT to Grant
❌ **Avoid these excessive permissions:**
- `roles/bigquery.admin` - Too broad, includes dataset/table creation
- `roles/editor` - Project-wide edit access
- `roles/owner` - Full project access
- `bigquery.datasets.create` - Not needed if dataset exists
- `bigquery.tables.create` - Not needed if table exists

## Security Features Implemented

### 1. Credential Validation
- Service account key format validation
- Project ID format validation (6-30 chars, lowercase, numbers, hyphens)
- Dataset/Table ID validation (1-1024 chars, letters, numbers, underscores)

### 2. SQL Injection Prevention
- All BigQuery identifiers validated before query construction
- Parameterized queries for local database access
- No user input directly interpolated into SQL

### 3. Data Exposure Protection
- Entity allowlist filtering (replaces permissive denylist)
- Attribute sanitization for sensitive data
- User-configurable export scope

### 4. Secure File Handling
- Temporary files created with restrictive permissions (0o600)
- Robust cleanup in all error scenarios
- Files stored in Home Assistant config directory (not tmpfs)

### 5. Rate Limiting
- 60-second cooldown between manual exports
- Prevention of concurrent export operations
- Resource usage protection

### 6. Security Audit Logging
- Structured security event logging
- Authentication success/failure tracking
- Export operation monitoring

## Deployment Security Checklist

### Pre-Deployment
- [ ] Create BigQuery dataset and table manually
- [ ] Create service account with minimal permissions
- [ ] Download service account key securely
- [ ] Store key in Home Assistant `secrets.yaml`
- [ ] Configure entity allowlist (start with empty list)

### Service Account Setup
```bash
# Create service account
gcloud iam service-accounts create bigquery-export \
    --display-name="BigQuery Export for Home Assistant"

# Grant minimal permissions to specific dataset
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:bigquery-export@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:bigquery-export@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"

# Create and download key
gcloud iam service-accounts keys create ~/bigquery-key.json \
    --iam-account=bigquery-export@PROJECT_ID.iam.gserviceaccount.com
```

### BigQuery Setup
```sql
-- Create dataset (do this manually, not via integration)
CREATE SCHEMA IF NOT EXISTS `PROJECT_ID.home_assistant` 
OPTIONS (
  location = 'US',
  description = 'Home Assistant sensor data'
);

-- Create table (do this manually, not via integration)
CREATE TABLE `PROJECT_ID.home_assistant.sensor_data` (
  entity_id STRING NOT NULL,
  state STRING,
  attributes JSON,
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

### Home Assistant Configuration
```yaml
# secrets.yaml
bigquery_service_account: |
  {
    "type": "service_account",
    "project_id": "your-project-id",
    "private_key_id": "...",
    "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
    "client_email": "bigquery-export@your-project-id.iam.gserviceaccount.com",
    "client_id": "...",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
```

## Entity Filtering Security

### Allowlist Configuration
Configure which entities to export using the integration's options:

```yaml
# Example allowlist patterns
allowed_entities:
  - "sensor.temperature_*"          # All temperature sensors
  - "sensor.humidity_*"             # All humidity sensors  
  - "binary_sensor.door_*"          # Door sensors
  - "light.living_room"             # Specific light

# Denied attributes (removes sensitive data)
denied_attributes:
  "device_tracker.*":               # Remove location data
    - "latitude"
    - "longitude"
    - "gps_accuracy"
  "person.*":                       # Remove personal info
    - "latitude"
    - "longitude"
    - "address"
```

### High-Risk Entities to Exclude
❌ **Never export these entity types:**
- `device_tracker.*` - Contains GPS coordinates
- `person.*` - Contains personal location data
- `alarm_control_panel.*` - Security system states
- `lock.*` - Lock states and access codes
- `camera.*` - Image data and streams
- `notify.*` - Notification content
- `input_text.*` - May contain passwords/secrets

## Security Updates

This integration implements security hardening based on the security audit findings:
- Fixed SQL injection vulnerability (services.py:790)
- Secured temporary file handling (services.py:661)
- Implemented credential validation
- Added rate limiting protection
- Replaced permissive denylist with secure allowlist filtering

## Contact

For security issues or questions:
- Report vulnerabilities via GitHub Issues
- Follow responsible disclosure practices
- Include detailed reproduction steps