# Home Assistant BigQuery Export Integration

## Project Overview
Create a Home Assistant custom integration that exports sensor data from the recorder database to Google BigQuery for long-term storage and AI/ML analysis. This will be published as a HACS (Home Assistant Community Store) plugin with enterprise-grade security.

## Architecture
- **Data Flow**: Home Assistant Recorder DB → Export Service → BigQuery → AI/ML Analysis
- **Authentication**: Google Cloud Service Account with OAuth2
- **Export Strategy**: Incremental exports with deduplication
- **Scheduling**: Configurable (weekly/monthly)
- **Target**: HACS-compatible custom integration

## Technical Requirements

### Storage Solution
- **Primary**: Google BigQuery (time-series optimized, ML integration)
- **Schema**: Partitioned by date, clustered by entity_id
- **Backup options**: InfluxDB Cloud, TimescaleDB

### Security Features
- Google Cloud Service Account authentication
- Minimal IAM permissions (BigQuery Data Editor only)
- Secure credential storage in Home Assistant
- Rate limiting and error handling
- Data validation before export

## Project Structure
```
ha-bigquery-export/
├── custom_components/bigquery_export/
│   ├── __init__.py              # Integration setup and entry point
│   ├── config_flow.py           # Configuration UI flow
│   ├── const.py                 # Constants and configuration
│   ├── coordinator.py           # Data coordination and state management
│   ├── services.py              # Export services and BigQuery operations
│   ├── manifest.json            # Integration metadata for HACS
│   └── translations/
│       └── en.json              # English translations
├── README.md                    # Installation and usage documentation
├── CHANGELOG.md                 # Version history
├── LICENSE                      # Open source license
└── requirements.txt             # Python dependencies
```

## Implementation Plan

### Phase 1: Core Functionality
1. **Basic Integration Setup**
   - Create Home Assistant custom integration structure
   - Implement basic BigQuery connection
   - Service account authentication
   - Manual export functionality

2. **Data Access Layer**
   - Query Home Assistant recorder database
   - Access `states` and `statistics` tables
   - Handle different entity types and data formats

3. **Export Engine**
   - Batch processing (1000-5000 records)
   - Basic error handling and logging
   - Simple data transformation

### Phase 2: Production Features
1. **Scheduled Exports**
   - Configurable timing (weekly/monthly)
   - Incremental sync with state tracking
   - Last export timestamp per entity

2. **Configuration UI**
   - Service account key upload
   - BigQuery project/dataset selection
   - Export schedule configuration
   - Entity filtering options

3. **Monitoring & Logging**
   - Export status tracking
   - Error reporting and notifications
   - Performance metrics

### Phase 3: Enterprise Features
1. **Advanced Configuration**
   - Multiple destination support
   - Data transformation options
   - Custom BigQuery schemas
   - Export filtering and entity selection

2. **Security Enhancements**
   - Key rotation support
   - Audit logging
   - Data encryption options

3. **HACS Publication**
   - Code quality validation
   - Documentation completion
   - Community feedback integration

## Key Files to Implement

### 1. `manifest.json`
```json
{
  "domain": "bigquery_export",
  "name": "BigQuery Export",
  "version": "1.0.0",
  "documentation": "https://github.com/[username]/ha-bigquery-export",
  "issue_tracker": "https://github.com/[username]/ha-bigquery-export/issues",
  "dependencies": [],
  "codeowners": ["@[username]"],
  "requirements": [
    "google-cloud-bigquery>=3.0.0",
    "google-auth>=2.0.0"
  ],
  "config_flow": true,
  "integration_type": "service"
}
```

### 2. `const.py`
```python
"""Constants for BigQuery Export integration."""
DOMAIN = "bigquery_export"
CONF_PROJECT_ID = "project_id"
CONF_DATASET_ID = "dataset_id"
CONF_TABLE_ID = "table_id"
CONF_SERVICE_ACCOUNT_KEY = "service_account_key"
CONF_EXPORT_SCHEDULE = "export_schedule"
CONF_ENTITIES = "entities"

DEFAULT_EXPORT_SCHEDULE = "weekly"
DEFAULT_BATCH_SIZE = 1000
```

### 3. `__init__.py`
```python
"""BigQuery Export integration for Home Assistant."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN
from .coordinator import BigQueryExportCoordinator

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BigQuery Export from a config entry."""
    coordinator = BigQueryExportCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

### 4. `config_flow.py`
```python
"""Config flow for BigQuery Export integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, CONF_PROJECT_ID, CONF_DATASET_ID, CONF_SERVICE_ACCOUNT_KEY

class BigQueryExportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BigQuery Export."""
    
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            # Validate BigQuery connection
            try:
                await self._validate_bigquery_connection(user_input)
                return self.async_create_entry(
                    title="BigQuery Export",
                    data=user_input
                )
            except Exception as err:
                errors["base"] = "cannot_connect"
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PROJECT_ID): str,
                vol.Required(CONF_DATASET_ID): str,
                vol.Required(CONF_SERVICE_ACCOUNT_KEY): str,
            }),
            errors=errors,
        )
```

### 5. `services.py`
```python
"""BigQuery export services."""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

from google.cloud import bigquery
from google.oauth2 import service_account
from homeassistant.components.recorder import get_instance
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class BigQueryExportService:
    """Service for exporting data to BigQuery."""
    
    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]):
        """Initialize the export service."""
        self.hass = hass
        self.config = config
        self._client = None
        
    async def async_setup(self):
        """Set up the BigQuery client."""
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(self.config[CONF_SERVICE_ACCOUNT_KEY])
        )
        self._client = bigquery.Client(
            credentials=credentials,
            project=self.config[CONF_PROJECT_ID]
        )
        
    async def async_export_data(self, start_time: datetime, end_time: datetime) -> bool:
        """Export data to BigQuery."""
        try:
            # Get recorder instance
            recorder = get_instance(self.hass)
            
            # Query states data
            states_data = await self._get_states_data(recorder, start_time, end_time)
            
            # Transform and load to BigQuery
            await self._load_to_bigquery(states_data)
            
            return True
        except Exception as err:
            _LOGGER.error("Error exporting data: %s", err)
            return False
```

### 6. `coordinator.py`
```python
"""Data update coordinator for BigQuery Export."""
import logging
from datetime import datetime, timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, DEFAULT_EXPORT_SCHEDULE
from .services import BigQueryExportService

_LOGGER = logging.getLogger(__name__)

class BigQueryExportCoordinator(DataUpdateCoordinator):
    """Coordinator for BigQuery Export."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        self.entry = entry
        self.export_service = BigQueryExportService(hass, entry.data)
        
    async def _async_update_data(self):
        """Update data."""
        # Check if export is due
        if self._is_export_due():
            await self.export_service.async_export_data(
                self._get_last_export_time(),
                datetime.now()
            )
```

## BigQuery Schema
```sql
CREATE TABLE `project.dataset.sensor_data` (
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

## Dependencies
```
google-cloud-bigquery>=3.0.0
google-auth>=2.0.0
google-auth-oauthlib>=1.0.0
```

## Development Commands
```bash
# Setup development environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Validate Home Assistant integration
hass --script check_config

# Run tests
python -m pytest tests/

# Package for HACS
zip -r bigquery_export.zip custom_components/
```

## HACS Publication Checklist
- [ ] Proper repository structure
- [ ] README with installation instructions
- [ ] Semantic versioning and release tags
- [ ] Code passes Home Assistant validation
- [ ] Configuration flow implemented
- [ ] Proper error handling
- [ ] Translation support
- [ ] Documentation complete
- [ ] License file included
- [ ] CHANGELOG.md maintained

## Testing Strategy
1. **Unit Tests**: Core functionality and data transformation
2. **Integration Tests**: Home Assistant integration points
3. **End-to-End Tests**: Full export workflow
4. **Performance Tests**: Large dataset handling
5. **Security Tests**: Authentication and data validation

## Success Metrics
- Successful data export to BigQuery
- No data loss during export
- Proper error handling and recovery
- User-friendly configuration
- HACS approval and publication
- Community adoption and feedback

## Next Steps
1. Create basic integration structure
2. Implement BigQuery connection and authentication
3. Build data export functionality
4. Add configuration UI
5. Implement scheduling and monitoring
6. Test and validate
7. Prepare for HACS publication

This integration will provide Home Assistant users with enterprise-grade long-term data storage and analytics capabilities, enabling advanced AI/ML analysis of their smart home data.