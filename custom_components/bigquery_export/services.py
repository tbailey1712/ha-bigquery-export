"""BigQuery export services."""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import os
import shutil
from datetime import datetime, timedelta
from typing import Any

import yaml
from google.cloud import bigquery
from google.oauth2 import service_account
from sqlalchemy import text

from homeassistant.components.recorder import get_instance
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    BIGQUERY_SCHEMA,
    CONF_ALLOWED_ENTITIES,
    CONF_DATASET_ID,
    CONF_DENIED_ATTRIBUTES,
    CONF_FILTERING_MODE,
    CONF_LAST_EXPORT_TIME,
    CONF_PROJECT_ID,
    CONF_SERVICE_ACCOUNT_KEY,
    CONF_TABLE_ID,
    DEFAULT_BATCH_SIZE,
    DEFAULT_TABLE_ID,
    DOMAIN,
    FILTERING_MODE_EXCLUDE,
    FILTERING_MODE_INCLUDE,
    DEFAULT_PRIORITY_SENSORS,
    NETWORK_SENSORS_TO_KEEP,
    EXCLUDE_NETWORK_PATTERNS,
    EXCLUDE_NETWORK_UNITS,
    KEEP_NETWORK_ESSENTIALS,
    EXCLUDE_OTHER_PATTERNS,
    GROW_TENT_ESSENTIALS,
)

_LOGGER = logging.getLogger(__name__)


# Import utility functions
from .utils import (
    _resolve_secret,
    validate_bigquery_identifiers,
    validate_service_account_key,
    should_export_entity,
    sanitize_attributes,
    log_security_event
)


def should_export_entity_legacy(entity_id: str, domain: str, unit_of_measurement: str = None) -> bool:
    """Legacy entity filtering - to be replaced with allowlist approach."""
    
    # Always include priority sensors
    if entity_id in DEFAULT_PRIORITY_SENSORS:
        return True
    
    # Include selective network sensors from legacy list
    if entity_id in NETWORK_SENSORS_TO_KEEP:
        return True
    
    # Include essential network sensors
    if entity_id in KEEP_NETWORK_ESSENTIALS:
        return True
    
    # Include essential grow tent sensors only
    if entity_id in GROW_TENT_ESSENTIALS:
        return True
        
    # Exclude by unit of measurement (network noise by units)
    if unit_of_measurement and unit_of_measurement in EXCLUDE_NETWORK_UNITS:
        return False
        
    # Exclude network noise patterns (aggressive filtering)
    for pattern in EXCLUDE_NETWORK_PATTERNS:
        if pattern in entity_id:
            return False
    
    # Exclude other noisy patterns (grow tent, etc.)
    for pattern in EXCLUDE_OTHER_PATTERNS:
        if pattern in entity_id:
            return False
    
    # Include all non-network sensors by default
    if not entity_id.startswith('sensor.') or 'network' not in entity_id:
        return True
        
    # Exclude remaining network sensors (the noisy ones)
    return False


class BigQueryExportService:
    """Service for exporting data to BigQuery."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any], entry=None) -> None:
        """Initialize the export service."""
        self.hass = hass
        self.config = config
        self.entry = entry
        self._client: bigquery.Client | None = None
        self._table_ref: bigquery.TableReference | None = None
        self._last_export_count: int = 0

    async def async_setup(self) -> None:
        """Set up the BigQuery client."""
        try:
            # Resolve secret reference if needed
            service_account_key = _resolve_secret(self.hass, self.config[CONF_SERVICE_ACCOUNT_KEY])
            
            # Validate service account key
            service_account_info = validate_service_account_key(service_account_key)
            
            # Validate BigQuery identifiers
            validate_bigquery_identifiers(
                self.config[CONF_PROJECT_ID],
                self.config[CONF_DATASET_ID],
                self.config.get(CONF_TABLE_ID, DEFAULT_TABLE_ID)
            )
            
            # Create credentials
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info
            )
            
            # Initialize BigQuery client
            self._client = bigquery.Client(
                credentials=credentials,
                project=self.config[CONF_PROJECT_ID]
            )
            
            # Set up table reference
            dataset_id = self.config[CONF_DATASET_ID]
            table_id = self.config.get(CONF_TABLE_ID, DEFAULT_TABLE_ID)
            self._table_ref = self._client.dataset(dataset_id).table(table_id)
            
            # Ensure table exists
            await self._ensure_table_exists()
            
            # Log security event
            log_security_event(
                self.hass,
                "bigquery_connection_success",
                {"project_id": self.config[CONF_PROJECT_ID]},
                "info"
            )
            
            _LOGGER.info("BigQuery export service initialized successfully")
            
        except ValueError as err:
            _LOGGER.error("Invalid configuration: %s", err)
            log_security_event(
                self.hass,
                "bigquery_connection_failed",
                {"error": "invalid_configuration", "project_id": self.config.get(CONF_PROJECT_ID)},
                "error"
            )
            raise
        except Exception as err:
            _LOGGER.error("Error setting up BigQuery export service", exc_info=True)
            log_security_event(
                self.hass,
                "bigquery_connection_failed",
                {"error": "connection_failed", "project_id": self.config.get(CONF_PROJECT_ID)},
                "error"
            )
            raise

    async def _ensure_table_exists(self) -> None:
        """Ensure the BigQuery table exists with proper schema."""
        def _create_table():
            try:
                # Check if table exists
                table = self._client.get_table(self._table_ref)
                _LOGGER.info("Table exists: %s", table.table_id)
                return table
            except Exception:
                # Table doesn't exist, create it
                _LOGGER.info("Creating table: %s", self._table_ref.table_id)
                
                # Create table schema
                schema = [
                    bigquery.SchemaField(field["name"], field["type"], field["mode"])
                    for field in BIGQUERY_SCHEMA
                ]
                
                # Create table
                table = bigquery.Table(self._table_ref, schema=schema)
                
                # Set up partitioning and clustering
                table.time_partitioning = bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY,
                    field="last_changed"
                )
                table.clustering_fields = ["entity_id", "domain"]
                
                # Create the table
                created_table = self._client.create_table(table)
                _LOGGER.info("Table created successfully: %s", created_table.table_id)
                return created_table
        
        # Run in executor to avoid blocking
        await self.hass.async_add_executor_job(_create_table)

    async def async_manual_export(
        self, 
        start_time: datetime | None = None, 
        end_time: datetime | None = None,
        days_back: int = 30,
        use_bulk_upload: bool = True,
        status_callback = None,
        chunk_size_days: int = 7,
        use_smart_chunking: bool = False
    ) -> bool:
        """Perform a manual export of data with automatic chunking.
        
        Args:
            start_time: Start time for export (optional)
            end_time: End time for export (optional, defaults to now)
            days_back: Number of days back to export if no times specified
            use_bulk_upload: If True, use bulk file upload for large datasets (>10K records)
            chunk_size_days: Maximum days per chunk (default: 7)
            use_smart_chunking: If True, avoid reprocessing already exported data (for incremental syncs)
        """
        _LOGGER.info("Manual export requested: %s to %s (%d days)", start_time, end_time, days_back)
        
        if status_callback:
            status_callback("connecting", "Validating BigQuery connection...")
        
        if not self._client:
            _LOGGER.error("BigQuery client not initialized")
            if status_callback:
                status_callback("failed", "BigQuery client not initialized")
            return False
        
        try:
            # Set default time range if not provided
            if end_time is None:
                end_time = dt_util.utcnow()
            
            if start_time is None:
                start_time = end_time - timedelta(days=days_back)
            
            _LOGGER.info("Export range: %s to %s", start_time, end_time)
            
            # Calculate total time range
            total_duration = end_time - start_time
            total_days = total_duration.days + (total_duration.seconds / 86400)
            
            # Determine if we need chunking
            if total_days > chunk_size_days:
                chunk_type = "smart" if use_smart_chunking else "regular"
                _LOGGER.info("Using %s chunking for %.1f days", chunk_type, total_days)
                
                if status_callback:
                    status_callback("planning", f"Planning {chunk_type} export: {total_days:.1f} days...")
                
                return await self._export_with_chunking(start_time, end_time, chunk_size_days, use_bulk_upload, status_callback, use_smart_chunking)
            else:
                _LOGGER.info("Using single export for %.1f days", total_days)
                
                if status_callback:
                    status_callback("analyzing", "Analyzing data range...")
                
                records_exported = await self._export_data_range(start_time, end_time, use_bulk_upload, status_callback)
                
                if status_callback:
                    status_callback("completed", f"Successfully exported {records_exported} records")
                
                self._last_export_count = records_exported
                _LOGGER.info("Manual export completed: %s records", records_exported)
                return True
            
        except Exception as err:
            _LOGGER.error("Error during manual export: %s", err, exc_info=True)
            if status_callback:
                status_callback("failed", f"Export failed: {str(err)}")
            return False

    async def _export_with_chunking(
        self,
        start_time: datetime,
        end_time: datetime,
        chunk_size_days: int,
        use_bulk_upload: bool,
        status_callback = None,
        use_smart_chunking: bool = False
    ) -> bool:
        """Export large time ranges by breaking them into smaller chunks."""
        chunk_type = "smart" if use_smart_chunking else "regular"
        _LOGGER.info("Starting %s chunked export from %s to %s", chunk_type, start_time, end_time)
        
        # Only use smart logic for incremental syncs, not manual historical exports
        if use_smart_chunking:
            # Get last successful export time to avoid reprocessing
            last_export_time = await self._get_last_export_time()
            
            # Adjust start time to avoid reprocessing already exported data
            if last_export_time and last_export_time >= start_time:
                start_time = last_export_time
                _LOGGER.info("Smart chunking: adjusting start time to %s (last export time)", start_time)
            
            # Check if there's actually any new data to export
            if start_time >= end_time:
                _LOGGER.info("No new data to export (last export: %s, end: %s)", start_time, end_time)
                if status_callback:
                    status_callback("completed", "No new data to export")
                self._last_export_count = 0
                return True
        
        total_records_exported = 0
        chunk_count = 0
        
        # Calculate total chunks for progress reporting
        total_duration = end_time - start_time
        total_days = total_duration.days + (total_duration.seconds / 86400)
        total_chunks = int((total_days + chunk_size_days - 1) // chunk_size_days)  # Round up
        
        _LOGGER.info("%s chunking: %d chunks of %d days each (%.1f days total)", 
                    chunk_type, total_chunks, chunk_size_days, total_days)
        
        # Process chunks from most recent to oldest
        current_end = end_time
        
        try:
            while current_end > start_time:
                chunk_count += 1
                current_start = max(start_time, current_end - timedelta(days=chunk_size_days))
                
                if status_callback:
                    chunk_duration = current_end - current_start
                    chunk_days = chunk_duration.days + (chunk_duration.seconds / 86400)
                    status_callback("chunking", 
                                  f"Processing chunk {chunk_count}/{total_chunks} ({chunk_days:.1f} days)...")
                
                # Export this chunk
                chunk_records = await self._export_data_range(
                    current_start, current_end, use_bulk_upload, 
                    lambda status, progress: status_callback("chunking", 
                        f"Chunk {chunk_count}/{total_chunks}: {progress}") if status_callback else None
                )
                
                total_records_exported += chunk_records
                _LOGGER.info("Chunk %d/%d completed: %s records", chunk_count, total_chunks, chunk_records)
                
                # Update last export time after successful chunk
                await self._update_last_export_time(current_end)
                
                # Move to next chunk (going backwards in time)
                current_end = current_start
                
                # Small delay between chunks to avoid overwhelming the database
                if chunk_count < total_chunks:
                    await asyncio.sleep(1)
            
            # Store the total export count
            self._last_export_count = total_records_exported
            
            if status_callback:
                status_callback("completed", 
                              f"{chunk_type.title()} export completed: {total_records_exported:,} records in {chunk_count} chunks")
            
            _LOGGER.info("%s chunked export completed: %s total records in %d chunks", 
                        chunk_type.title(), total_records_exported, chunk_count)
            return True
            
        except Exception as err:
            _LOGGER.error("Error during chunked export at chunk %d/%d: %s", chunk_count, total_chunks, err)
            if status_callback:
                status_callback("failed", f"Chunked export failed at chunk {chunk_count}/{total_chunks}: {str(err)}")
            return False

    async def _get_last_export_time(self) -> datetime | None:
        """Get the timestamp of the last successful export."""
        try:
            # Query BigQuery to get the latest export_timestamp
            query = f"""
                SELECT MAX(export_timestamp) as last_export
                FROM `{self._table_ref.project}.{self._table_ref.dataset_id}.{self._table_ref.table_id}`
            """
            
            def _query():
                query_job = self._client.query(query)
                results = query_job.result()
                for row in results:
                    return row.last_export
                return None
            
            last_export = await self.hass.async_add_executor_job(_query)
            
            if last_export:
                _LOGGER.info("Last export time found: %s", last_export)
                return last_export
            else:
                _LOGGER.info("No previous exports found")
                return None
                
        except Exception as err:
            _LOGGER.warning("Could not determine last export time: %s", err)
            return None

    async def _update_last_export_time(self, export_time: datetime) -> None:
        """Update the last export time in our tracking."""
        # For now, this is handled by the export_timestamp column in BigQuery
        # In the future, we could also store this in Home Assistant config
        pass

    async def async_incremental_export(self) -> bool:
        """Perform an incremental export based on last export time."""
        _LOGGER.info("Starting incremental export")
        
        try:
            # Get last export time from persistent storage
            last_export_time = self.config.get(CONF_LAST_EXPORT_TIME)
            
            if last_export_time:
                try:
                    start_time = datetime.fromisoformat(last_export_time)
                except ValueError:
                    _LOGGER.warning("Invalid last export time format, starting from 7 days ago")
                    start_time = dt_util.utcnow() - timedelta(days=7)
            else:
                # First export, get data from the last 7 days
                start_time = dt_util.utcnow() - timedelta(days=7)
                _LOGGER.info("First incremental export, starting from 7 days ago")
            
            end_time = dt_util.utcnow()
            
            # Ensure we don't have gaps - subtract 1 minute from start time for overlap
            start_time = start_time - timedelta(minutes=1)
            
            _LOGGER.info("Incremental export range: %s to %s", start_time, end_time)
            
            records_exported = await self._export_data_range(start_time, end_time)
            
            # Only update last export time if export was successful
            if records_exported >= 0:  # Even 0 records is a successful export
                self.config[CONF_LAST_EXPORT_TIME] = end_time.isoformat()
                # Persist the updated config
                await self._update_config_entry()
            
            _LOGGER.info("Incremental export completed: %d records exported", records_exported)
            return True
            
        except Exception as err:
            _LOGGER.error("Error during incremental export: %s", err)
            return False

    async def _update_config_entry(self) -> None:
        """Update the config entry with current configuration."""
        def _update():
            # Update config entry in Home Assistant
            self.hass.config_entries.async_update_entry(
                # Find the config entry for our integration
                next(
                    entry for entry in self.hass.config_entries.async_entries(DOMAIN)
                    if entry.data.get(CONF_PROJECT_ID) == self.config[CONF_PROJECT_ID]
                ),
                data=self.config
            )
        
        # Run in main thread
        self.hass.add_job(_update)

    async def _export_data_range(
        self, start_time: datetime, end_time: datetime, use_bulk_upload: bool = True, status_callback = None
    ) -> int:
        """Export data for a specific time range."""
        _LOGGER.info("Exporting data range: %s to %s", start_time, end_time)
        
        # Get recorder instance
        recorder = get_instance(self.hass)
        if not recorder:
            _LOGGER.error("Recorder not available")
            raise RuntimeError("Recorder not available")
        
        def _query_and_export():
            total_records = 0
            
            # Set export timestamp once for this entire export operation
            export_timestamp = dt_util.utcnow().isoformat()
            
            # Store the callback reference for use within the executor
            nonlocal status_callback
            
            # Query data in batches
            with recorder.get_session() as session:
                # Check total records for reference
                count_query = text("SELECT COUNT(*) as total FROM states")
                count_result = session.execute(count_query)
                total_count = count_result.scalar()
                _LOGGER.info("Total records in states table: %s", total_count)
                
                
                # Convert our datetime range to Unix timestamps
                start_timestamp = start_time.timestamp()
                end_timestamp = end_time.timestamp()
                
                # Check how many records we have in this time range
                test_query = text("SELECT COUNT(*) as count FROM states WHERE last_updated_ts >= :start_ts AND last_updated_ts < :end_ts")
                test_result = session.execute(test_query, {"start_ts": start_timestamp, "end_ts": end_timestamp})
                test_count = test_result.scalar()
                _LOGGER.info("Records in time range: %s", test_count)
                
                if test_count == 0:
                    _LOGGER.warning("No data found in timestamp range")
                    return 0
                
                # Decide between bulk upload and batch processing
                bulk_upload_threshold = 10000  # Use bulk upload for >10K records
                if use_bulk_upload and test_count > bulk_upload_threshold:
                    _LOGGER.info("Large dataset (%d records), using bulk file upload", test_count)
                    
                    # Check disk space before creating large temp file
                    estimated_file_size = test_count * 400  # ~400 bytes per record
                    estimated_gb = estimated_file_size / (1024**3)
                    
                    # Get available disk space (use HA data directory instead of tmpfs)
                    ha_data_dir = self.hass.config.path()
                    free_space = shutil.disk_usage(ha_data_dir).free
                    free_gb = free_space / (1024**3)
                    
                    _LOGGER.info("Estimated temp file: %.1f GB, Available space: %.1f GB", estimated_gb, free_gb)
                    
                    # Require at least 2x the estimated file size for safety
                    if free_space < (estimated_file_size * 2):
                        error_msg = f"Insufficient disk space! Need ~{estimated_gb:.1f}GB, only {free_gb:.1f}GB available"
                        _LOGGER.error(error_msg)
                        if status_callback:
                            status_callback("failed", error_msg)
                        raise RuntimeError(error_msg)
                    
                    if status_callback:
                        status_callback("exporting", f"Creating {estimated_gb:.1f}GB export file for {test_count:,} records...")
                    return self._bulk_export_via_file(session, start_timestamp, end_timestamp, status_callback)
                else:
                    _LOGGER.info("Using batch processing for %d records", test_count)
                    if status_callback:
                        status_callback("exporting", f"Processing {test_count:,} records in batches...")
                    
                # Use proper schema with joins to get entity_id and attributes
                query = text("""
                    SELECT 
                        s.state,
                        s.last_updated_ts,
                        s.last_changed_ts,
                        s.last_reported_ts,
                        s.context_id,
                        s.context_user_id,
                        s.metadata_id,
                        m.entity_id,
                        sa.shared_attrs as attributes
                    FROM states s
                    JOIN states_meta m ON s.metadata_id = m.metadata_id
                    LEFT JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
                    WHERE s.last_updated_ts >= :start_ts 
                    AND s.last_updated_ts < :end_ts
                    ORDER BY s.last_updated_ts
                """)
                
                result = session.execute(
                    query,
                    {
                        "start_ts": start_timestamp,
                        "end_ts": end_timestamp,
                    }
                )
                
                # Immediately materialize all results while session is active
                db_rows = result.fetchall()
                _LOGGER.info("Fetched %d rows from database", len(db_rows))
                
                # Get filtering configuration once before loop
                if self.entry:
                    filtering_mode = self.entry.options.get(CONF_FILTERING_MODE, FILTERING_MODE_EXCLUDE)
                    allowed_entities = self.entry.options.get(CONF_ALLOWED_ENTITIES, [])
                    denied_attributes = self.entry.options.get(CONF_DENIED_ATTRIBUTES, {})
                else:
                    filtering_mode = self.config.get(CONF_FILTERING_MODE, FILTERING_MODE_EXCLUDE)
                    allowed_entities = self.config.get(CONF_ALLOWED_ENTITIES, [])
                    denied_attributes = self.config.get(CONF_DENIED_ATTRIBUTES, {})
                
                # Debug logging once before processing
                _LOGGER.info("Filtering mode: %s, Allowed entities count: %d", filtering_mode, len(allowed_entities))
                if allowed_entities:
                    _LOGGER.info("First 3 patterns: %s", allowed_entities[:3])
                
                # Process results in batches
                rows = []
                row_count = 0
                filtered_count = 0
                for row in db_rows:
                    row_count += 1
                    if row_count % 100000 == 0:  # Only log every 100K records
                        _LOGGER.info("Export progress: %d rows processed", row_count)
                    
                    # Parse attributes JSON
                    attributes = {}
                    if row.attributes:
                        try:
                            attributes = json.loads(row.attributes)
                        except json.JSONDecodeError:
                            _LOGGER.warning("Failed to parse attributes for entity %s", row.entity_id)
                    
                    # Convert timestamps to datetime objects
                    last_updated = datetime.fromtimestamp(row.last_updated_ts, tz=dt_util.UTC) if row.last_updated_ts else None
                    last_changed = datetime.fromtimestamp(row.last_changed_ts, tz=dt_util.UTC) if row.last_changed_ts else last_updated
                    last_reported = datetime.fromtimestamp(row.last_reported_ts, tz=dt_util.UTC) if row.last_reported_ts else None
                    
                    # Extract domain from entity_id (states_meta doesn't have domain column)
                    domain = row.entity_id.split('.')[0] if '.' in row.entity_id else None
                    
                    # Extract unit from attributes for filtering
                    unit_of_measurement = attributes.get('unit_of_measurement')
                    
                    # Apply filtering based on mode
                    should_export = False
                    if filtering_mode == FILTERING_MODE_INCLUDE:
                        # Include only mode - use allowlist
                        should_export = should_export_entity(row.entity_id, allowed_entities)
                    else:
                        # Export all mode - start with "export everything", then apply exclusions
                        should_export = True
                        
                        # Apply user-configured exclusions if specified
                        if allowed_entities:
                            # In exclude mode, allowed_entities acts as exclusion patterns
                            # If entity matches any exclusion pattern, don't export it
                            if should_export_entity(row.entity_id, allowed_entities):
                                should_export = False
                    
                    if not should_export:
                        filtered_count += 1
                        continue  # Skip this entity
                    
                    # Sanitize attributes to remove sensitive data
                    attributes = sanitize_attributes(row.entity_id, attributes, denied_attributes)
                    
                    # Extract friendly_name
                    friendly_name = attributes.get('friendly_name', row.entity_id)
                    
                    # Create BigQuery row (convert datetime objects to ISO strings)
                    bq_row = {
                        "entity_id": row.entity_id,
                        "state": row.state,
                        "attributes": json.dumps(attributes) if attributes else None,  # Convert to JSON string
                        "last_changed": last_changed.isoformat() if last_changed else None,
                        "last_updated": last_updated.isoformat() if last_updated else None,
                        "context_id": row.context_id,
                        "context_user_id": row.context_user_id,
                        "domain": domain,
                        "friendly_name": friendly_name,
                        "unit_of_measurement": unit_of_measurement,
                        "export_timestamp": export_timestamp,
                    }
                    
                    rows.append(bq_row)
                    
                    # Insert batch when we reach the batch size
                    if len(rows) >= DEFAULT_BATCH_SIZE:
                        if status_callback:
                            batch_num = (total_records // DEFAULT_BATCH_SIZE) + 1
                            status_callback("uploading", f"Uploading batch {batch_num} ({total_records + len(rows):,} records processed)")
                        self._insert_batch(rows)
                        total_records += len(rows)
                        rows = []
                
                _LOGGER.info("Entity filtering: %d rows processed, %d filtered out, %d remaining for export", row_count, filtered_count, row_count - filtered_count)
                
                # Insert remaining rows
                if rows:
                    self._insert_batch(rows)
                    total_records += len(rows)
                
                _LOGGER.info("Export completed with %d total records", total_records)
            return total_records
        
        # Run in executor to avoid blocking
        return await self.hass.async_add_executor_job(_query_and_export)

    def _bulk_export_via_file(self, session, start_timestamp: float, end_timestamp: float, status_callback = None) -> int:
        """Export large datasets using JSONL file upload to BigQuery with MERGE deduplication."""
        _LOGGER.info("Starting bulk export via file with MERGE deduplication")
        
        # Set export timestamp once for this entire export operation
        export_timestamp = dt_util.utcnow().isoformat()
        
        temp_file_path = None
        try:
            # Create temporary JSONL file in HA data directory instead of tmpfs
            ha_data_dir = self.hass.config.path()
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, dir=ha_data_dir) as temp_file:
                temp_file_path = temp_file.name
                
                # Set restrictive permissions (owner read/write only)
                os.chmod(temp_file_path, 0o600)
                
                # Query data using same query as batch processing
                query = text("""
                    SELECT 
                        s.state,
                        s.last_updated_ts,
                        s.last_changed_ts,
                        s.last_reported_ts,
                        s.context_id,
                        s.context_user_id,
                        s.metadata_id,
                        m.entity_id,
                        sa.shared_attrs as attributes
                    FROM states s
                    JOIN states_meta m ON s.metadata_id = m.metadata_id
                    LEFT JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
                    WHERE s.last_updated_ts >= :start_ts 
                    AND s.last_updated_ts < :end_ts
                    ORDER BY s.last_updated_ts
                """)
                
                result = session.execute(query, {"start_ts": start_timestamp, "end_ts": end_timestamp})
                
                # Write records to JSONL file
                record_count = 0
                filtered_count = 0
                
                # Get filtering configuration once before loop
                if self.entry:
                    filtering_mode = self.entry.options.get(CONF_FILTERING_MODE, FILTERING_MODE_EXCLUDE)
                    allowed_entities = self.entry.options.get(CONF_ALLOWED_ENTITIES, [])
                    denied_attributes = self.entry.options.get(CONF_DENIED_ATTRIBUTES, {})
                else:
                    filtering_mode = self.config.get(CONF_FILTERING_MODE, FILTERING_MODE_EXCLUDE)
                    allowed_entities = self.config.get(CONF_ALLOWED_ENTITIES, [])
                    denied_attributes = self.config.get(CONF_DENIED_ATTRIBUTES, {})
                
                # Debug logging once before processing
                _LOGGER.info("Filtering mode: %s, Allowed entities count: %d", filtering_mode, len(allowed_entities))
                if allowed_entities:
                    _LOGGER.info("First 3 patterns: %s", allowed_entities[:3])
                
                for row in result:
                    record_count += 1
                    if record_count % 100000 == 0:  # Log every 100K records
                        if status_callback:
                            status_callback("exporting", f"Processing {record_count:,} records...")
                        _LOGGER.info("Export progress: %d records processed, %d filtered", record_count, filtered_count)
                    
                    # Parse attributes JSON
                    attributes = {}
                    if row.attributes:
                        try:
                            attributes = json.loads(row.attributes)
                        except json.JSONDecodeError:
                            _LOGGER.warning("Failed to parse attributes for entity %s", row.entity_id)
                    
                    # Convert timestamps to datetime objects then to ISO strings
                    last_updated = datetime.fromtimestamp(row.last_updated_ts, tz=dt_util.UTC) if row.last_updated_ts else None
                    last_changed = datetime.fromtimestamp(row.last_changed_ts, tz=dt_util.UTC) if row.last_changed_ts else last_updated
                    
                    # Extract domain from entity_id
                    domain = row.entity_id.split('.')[0] if '.' in row.entity_id else None
                    
                    # Extract unit from attributes for filtering
                    unit_of_measurement = attributes.get('unit_of_measurement')
                    
                    # Apply filtering based on mode
                    should_export = False
                    if filtering_mode == FILTERING_MODE_INCLUDE:
                        # Include only mode - use allowlist
                        should_export = should_export_entity(row.entity_id, allowed_entities)
                    else:
                        # Export all mode - start with "export everything", then apply exclusions
                        should_export = True
                        
                        # Apply user-configured exclusions if specified
                        if allowed_entities:
                            # In exclude mode, allowed_entities acts as exclusion patterns
                            # If entity matches any exclusion pattern, don't export it
                            if should_export_entity(row.entity_id, allowed_entities):
                                should_export = False
                    
                    if not should_export:
                        filtered_count += 1
                        continue  # Skip this entity
                    
                    # Sanitize attributes to remove sensitive data
                    attributes = sanitize_attributes(row.entity_id, attributes, denied_attributes)
                    
                    # Extract friendly_name
                    friendly_name = attributes.get('friendly_name', row.entity_id)
                    
                    # Create record for JSONL file
                    record = {
                        "entity_id": row.entity_id,
                        "state": row.state,
                        "attributes": json.dumps(attributes) if attributes else None,  # Convert to JSON string
                        "last_changed": last_changed.isoformat() if last_changed else None,
                        "last_updated": last_updated.isoformat() if last_updated else None,
                        "context_id": row.context_id,
                        "context_user_id": row.context_user_id,
                        "domain": domain,
                        "friendly_name": friendly_name,
                        "unit_of_measurement": unit_of_measurement,
                        "export_timestamp": export_timestamp,
                    }
                    
                    # Write as JSONL (one JSON object per line)
                    temp_file.write(json.dumps(record) + '\n')
                
                _LOGGER.info("Entity filtering: %d rows processed, %d filtered out, %d written to file", record_count + filtered_count, filtered_count, record_count)
            
            # Create temporary table name for bulk import
            temp_table_id = f"temp_bulk_export_{int(dt_util.utcnow().timestamp())}"
            temp_table_ref = self._client.dataset(self._table_ref.dataset_id).table(temp_table_id)
            
            try:
                # Create temporary table with same schema
                temp_table = bigquery.Table(temp_table_ref)
                temp_table.schema = self._client.get_table(self._table_ref).schema
                temp_table = self._client.create_table(temp_table)
                
                # Upload file to temporary table
                if status_callback:
                    status_callback("uploading", f"Uploading {record_count:,} records to temporary table...")
                
                job_config = bigquery.LoadJobConfig(
                    source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                    create_disposition=bigquery.CreateDisposition.CREATE_NEVER,
                )
                
                with open(temp_file_path, 'rb') as source_file:
                    load_job = self._client.load_table_from_file(
                        source_file,
                        temp_table_ref,
                        job_config=job_config
                    )
                
                # Wait for the load job to complete
                if status_callback:
                    status_callback("processing", "Waiting for BigQuery to process upload...")
                load_job.result()
                
                if load_job.errors:
                    _LOGGER.error("BigQuery load job errors: %s", load_job.errors)
                    raise RuntimeError(f"BigQuery load job failed: {load_job.errors}")
                
                # MERGE from temp table to main table (deduplication)
                if status_callback:
                    status_callback("merging", f"Merging {record_count:,} records with deduplication...")
                
                # Validate identifiers before using in query to prevent SQL injection
                validate_bigquery_identifiers(
                    self._table_ref.project,
                    self._table_ref.dataset_id,
                    self._table_ref.table_id
                )
                validate_bigquery_identifiers(
                    temp_table_ref.project,
                    temp_table_ref.dataset_id,
                    temp_table_ref.table_id
                )
                
                merge_query = f"""
                MERGE `{self._table_ref.project}.{self._table_ref.dataset_id}.{self._table_ref.table_id}` AS target
                USING `{temp_table_ref.project}.{temp_table_ref.dataset_id}.{temp_table_ref.table_id}` AS source
                ON target.entity_id = source.entity_id 
                   AND target.last_changed = source.last_changed
                WHEN NOT MATCHED THEN
                  INSERT (
                    entity_id, state, attributes, last_changed, last_updated,
                    context_id, context_user_id, domain, friendly_name,
                    unit_of_measurement, export_timestamp
                  )
                  VALUES (
                    source.entity_id, source.state, source.attributes,
                    source.last_changed, source.last_updated, source.context_id,
                    source.context_user_id, source.domain, source.friendly_name,
                    source.unit_of_measurement, source.export_timestamp
                  )
                """
                
                # Execute MERGE query
                merge_job = self._client.query(merge_query)
                merge_result = merge_job.result()
                
                # Get merge statistics if available
                if hasattr(merge_job, 'dml_stats') and merge_job.dml_stats:
                    inserted_rows = merge_job.dml_stats.inserted_row_count
                    _LOGGER.info("Bulk export completed: %d records processed, %d new rows inserted", record_count, inserted_rows)
                    if status_callback:
                        duplicates_skipped = record_count - inserted_rows
                        status_callback("completed", f"Merged {record_count:,} records: {inserted_rows} new, {duplicates_skipped} duplicates skipped")
                else:
                    _LOGGER.info("Bulk export completed: %d records processed", record_count)
                    if status_callback:
                        status_callback("completed", f"Merged {record_count:,} records with deduplication")
                return record_count
                
            finally:
                # Clean up temporary table
                try:
                    self._client.delete_table(temp_table_ref)
                except Exception as cleanup_err:
                    _LOGGER.warning("Failed to clean up temp table: %s", cleanup_err)
            
        except Exception as err:
            _LOGGER.error("Error during bulk export: %s", err, exc_info=True)
            raise
        finally:
            # Clean up temporary file - ensure robust cleanup
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError as cleanup_err:
                    _LOGGER.error("Error cleaning up temporary file %s: %s", temp_file_path, cleanup_err)

    def _insert_batch(self, rows: list[dict[str, Any]]) -> None:
        """Insert a batch of rows into BigQuery with deduplication."""
        try:
            # Create a temporary table name for this batch
            temp_table_id = f"temp_export_{int(dt_util.utcnow().timestamp())}"
            temp_table_ref = self._client.dataset(self._table_ref.dataset_id).table(temp_table_id)
            
            # Create temporary table with same schema
            temp_table = bigquery.Table(temp_table_ref)
            temp_table.schema = self._client.get_table(self._table_ref).schema
            temp_table = self._client.create_table(temp_table)
            
            try:
                # Insert rows into temporary table
                errors = self._client.insert_rows_json(
                    temp_table_ref,
                    rows,
                    ignore_unknown_values=True
                )
                
                if errors:
                    _LOGGER.error("BigQuery temp table insert errors: %s", errors)
                    raise RuntimeError(f"BigQuery temp table insert errors: {errors}")
                
                # MERGE from temp table to main table (deduplication)
                # Validate identifiers before using in query to prevent SQL injection
                validate_bigquery_identifiers(
                    self._table_ref.project,
                    self._table_ref.dataset_id,
                    self._table_ref.table_id
                )
                validate_bigquery_identifiers(
                    temp_table_ref.project,
                    temp_table_ref.dataset_id,
                    temp_table_ref.table_id
                )
                
                merge_query = f"""
                MERGE `{self._table_ref.project}.{self._table_ref.dataset_id}.{self._table_ref.table_id}` AS target
                USING `{temp_table_ref.project}.{temp_table_ref.dataset_id}.{temp_table_ref.table_id}` AS source
                ON target.entity_id = source.entity_id 
                   AND target.last_changed = source.last_changed
                WHEN NOT MATCHED THEN
                  INSERT (
                    entity_id, state, attributes, last_changed, last_updated,
                    context_id, context_user_id, domain, friendly_name,
                    unit_of_measurement, export_timestamp
                  )
                  VALUES (
                    source.entity_id, source.state, source.attributes,
                    source.last_changed, source.last_updated, source.context_id,
                    source.context_user_id, source.domain, source.friendly_name,
                    source.unit_of_measurement, source.export_timestamp
                  )
                """
                
                # Execute MERGE query
                query_job = self._client.query(merge_query)
                query_job.result()  # Wait for completion
                
                
            finally:
                # Clean up temporary table
                self._client.delete_table(temp_table_ref)
            
        except Exception as err:
            _LOGGER.error("Error inserting batch to BigQuery: %s", err, exc_info=True)
            raise

    async def async_test_connection(self) -> bool:
        """Test the BigQuery connection."""
        def _test():
            try:
                if not self._client:
                    raise RuntimeError("BigQuery client not initialized")
                
                # Test by listing datasets
                datasets = list(self._client.list_datasets(max_results=1))
                _LOGGER.info("BigQuery connection test successful")
                return True
                
            except Exception as err:
                _LOGGER.error("BigQuery connection test failed: %s", err)
                return False
        
        return await self.hass.async_add_executor_job(_test)

    def get_export_status(self) -> dict[str, Any]:
        """Get the current export status."""
        return {
            "last_export": self.config.get(CONF_LAST_EXPORT_TIME),
            "project_id": self.config[CONF_PROJECT_ID],
            "dataset_id": self.config[CONF_DATASET_ID],
            "table_id": self.config.get(CONF_TABLE_ID, DEFAULT_TABLE_ID),
            "connection_status": "connected" if self._client else "disconnected",
        }