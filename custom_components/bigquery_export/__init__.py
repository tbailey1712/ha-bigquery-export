"""BigQuery Export integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SERVICE_MANUAL_EXPORT,
    SERVICE_INCREMENTAL_EXPORT,
    SERVICE_CHECK_DATABASE_RETENTION,
    SERVICE_CHECK_STATISTICS_RETENTION,
    SERVICE_ANALYZE_EXPORT_STATUS,
    SERVICE_FIND_DATA_GAPS,
    SERVICE_ESTIMATE_BACKFILL,
)
from .coordinator import BigQueryExportCoordinator
from .services import BigQueryExportService

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BigQuery Export from a config entry."""
    _LOGGER.debug("Setting up BigQuery Export integration")
    
    # Initialize the export service
    export_service = BigQueryExportService(hass, entry.data, entry)
    
    # Store service in hass.data BEFORE coordinator initialization
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "service": export_service,
    }
    
    # Initialize the coordinator
    coordinator = BigQueryExportCoordinator(hass, entry)
    
    try:
        await export_service.async_setup()
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Error setting up BigQuery Export: %s", err)
        raise ConfigEntryNotReady(f"Error setting up BigQuery Export: {err}") from err
    
    # Add coordinator to hass.data
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator
    
    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await _async_register_services(hass, export_service)
    
    _LOGGER.info("BigQuery Export integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading BigQuery Export integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Remove from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove services if this was the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_MANUAL_EXPORT)
            hass.services.async_remove(DOMAIN, SERVICE_INCREMENTAL_EXPORT)
            hass.services.async_remove(DOMAIN, SERVICE_CHECK_DATABASE_RETENTION)
            hass.services.async_remove(DOMAIN, SERVICE_CHECK_STATISTICS_RETENTION)
            hass.services.async_remove(DOMAIN, SERVICE_ANALYZE_EXPORT_STATUS)
            hass.services.async_remove(DOMAIN, SERVICE_FIND_DATA_GAPS)
            hass.services.async_remove(DOMAIN, SERVICE_ESTIMATE_BACKFILL)
    
    return unload_ok


async def _async_register_services(
    hass: HomeAssistant, export_service: BigQueryExportService
) -> None:
    """Register integration services."""
    
    async def handle_manual_export(call):
        """Handle manual export service call."""
        _LOGGER.info("Manual export service called")

        # Get the coordinator for this integration
        coordinator = None
        for entry_id, data in hass.data[DOMAIN].items():
            if "coordinator" in data:
                coordinator = data["coordinator"]
                break

        if not coordinator:
            _LOGGER.error("Could not find coordinator for manual export")
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": "Could not find BigQuery Export coordinator",
                    "title": "BigQuery Export Failed",
                    "notification_id": "bigquery_export_error"
                }
            )
            return

        # Extract optional parameters
        days_back = call.data.get("days_back", 30)
        start_time = call.data.get("start_time")
        end_time = call.data.get("end_time")

        # Convert string dates to datetime if provided
        if start_time:
            start_time = dt_util.parse_datetime(start_time)
        if end_time:
            end_time = dt_util.parse_datetime(end_time)

        # Call the coordinator's manual export method
        success = await coordinator.async_manual_export(
            start_time=start_time,
            end_time=end_time,
            days_back=days_back
        )

        # Create persistent notification with status
        if success:
            _LOGGER.info("Manual export completed successfully")
            records = getattr(export_service, '_last_export_count', 0)
            start_str = start_time.strftime("%Y-%m-%d %H:%M") if start_time else f"{days_back} days ago"
            end_str = end_time.strftime("%Y-%m-%d %H:%M") if end_time else "now"

            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"**Records Exported:** {records:,}\n"
                               f"**Time Range:** {start_str} to {end_str}\n"
                               f"**Completed:** {dt_util.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "title": "✅ BigQuery Export Completed",
                    "notification_id": "bigquery_export_success"
                }
            )
        else:
            _LOGGER.error("Manual export failed")
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"Export failed. Check logs for details.\n"
                               f"**Time:** {dt_util.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "title": "❌ BigQuery Export Failed",
                    "notification_id": "bigquery_export_failed"
                }
            )
    
    async def handle_incremental_export(call):
        """Handle incremental export service call."""
        _LOGGER.info("Incremental export service called")

        # Get the coordinator for this integration
        coordinator = None
        for entry_id, data in hass.data[DOMAIN].items():
            if "coordinator" in data:
                coordinator = data["coordinator"]
                break

        if not coordinator:
            _LOGGER.error("Could not find coordinator for incremental export")
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": "Could not find BigQuery Export coordinator",
                    "title": "BigQuery Incremental Export Failed",
                    "notification_id": "bigquery_export_error"
                }
            )
            return

        # Call the service directly since incremental export doesn't need coordinator stats
        success = await export_service.async_incremental_export()

        # Create persistent notification with status
        if success:
            _LOGGER.info("Incremental export completed successfully")
            records = getattr(export_service, '_last_export_count', 0)
            last_export = getattr(export_service, '_last_export_time', None)
            last_export_str = last_export.strftime("%Y-%m-%d %H:%M") if last_export else "N/A"

            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"**Records Exported:** {records:,}\n"
                               f"**Since:** {last_export_str}\n"
                               f"**Completed:** {dt_util.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "title": "✅ BigQuery Incremental Export Completed",
                    "notification_id": "bigquery_export_incremental_success"
                }
            )
            # Trigger coordinator refresh to update sensor
            await coordinator.async_refresh()
        else:
            _LOGGER.error("Incremental export failed")
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"Incremental export failed. Check logs for details.\n"
                               f"**Time:** {dt_util.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "title": "❌ BigQuery Incremental Export Failed",
                    "notification_id": "bigquery_export_incremental_failed"
                }
            )
    
    # Handle database retention check
    async def handle_check_database_retention(call):
        """Handle the check_database_retention service call."""
        _LOGGER.info("Checking database retention...")

        result = await export_service.async_check_database_retention()

        if result and result[0] is not None:
            oldest_date, newest_date, days_of_data, total_records = result

            _LOGGER.info(f"Database retention: {oldest_date} to {newest_date} ({days_of_data} days, {total_records:,} records)")

            # Update the retention sensor
            for entry_id, data in hass.data[DOMAIN].items():
                if "sensors" in data and "retention" in data["sensors"]:
                    retention_sensor = data["sensors"]["retention"]
                    await retention_sensor.async_update_data(result)
                    break

            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"**Oldest Data:** {oldest_date}\n"
                               f"**Newest Data:** {newest_date}\n"
                               f"**Days of Data:** {days_of_data} days\n"
                               f"**Total Records:** {total_records:,}\n\n"
                               f"Check sensor: `sensor.local_database_retention`",
                    "title": "📊 Database Retention Check",
                    "notification_id": "bigquery_database_retention"
                }
            )
        else:
            _LOGGER.error("Failed to check database retention")
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": "Failed to query database. Check logs for details.",
                    "title": "❌ Database Retention Check Failed",
                    "notification_id": "bigquery_database_retention_failed"
                }
            )

    # Handle statistics retention check
    async def handle_check_statistics_retention(call):
        """Handle the check_statistics_retention service call."""
        _LOGGER.info("Checking statistics table retention...")

        result = await export_service.async_check_statistics_retention()

        if result and result[0] is not None:
            oldest_date, newest_date, days_of_data, total_records = result

            _LOGGER.info(f"Statistics retention: {oldest_date} to {newest_date} ({days_of_data} days, {total_records:,} records)")

            # Update the statistics sensor
            for entry_id, data in hass.data[DOMAIN].items():
                if "sensors" in data and "statistics" in data["sensors"]:
                    statistics_sensor = data["sensors"]["statistics"]
                    await statistics_sensor.async_update_data(result)
                    break

            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"**Oldest Stat:** {oldest_date}\n"
                               f"**Newest Stat:** {newest_date}\n"
                               f"**Days of Stats:** {days_of_data} days\n"
                               f"**Total Records:** {total_records:,}\n\n"
                               f"**Note:** The statistics table stores aggregated long-term data.\n"
                               f"This is likely what you're seeing in History graphs!",
                    "title": "📊 Statistics Table Check",
                    "notification_id": "bigquery_statistics_retention"
                }
            )
        else:
            _LOGGER.error("Failed to check statistics retention")
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": "Failed to query statistics table. Check logs for details.",
                    "title": "❌ Statistics Check Failed",
                    "notification_id": "bigquery_statistics_failed"
                }
            )

    # Handle analyze export status
    async def handle_analyze_export_status(call):
        """Handle the analyze_export_status service call."""
        _LOGGER.info("Analyzing export status...")

        result = await export_service.async_analyze_export_status()

        if result:
            # Update the coverage sensor
            for entry_id, data in hass.data[DOMAIN].items():
                if "sensors" in data and "coverage" in data["sensors"]:
                    coverage_sensor = data["sensors"]["coverage"]
                    await coverage_sensor.async_update_data(result)
                    break
            message = (
                f"## Local Database\n"
                f"- **Range:** {result['local_oldest']} to {result['local_newest']}\n"
                f"- **Days:** {result['local_days']}\n"
                f"- **Records:** {result['local_records']:,}\n\n"
                f"## BigQuery\n"
                f"- **Range:** {result['bigquery_oldest']} to {result['bigquery_newest']}\n"
                f"- **Days:** {result['bigquery_days']}\n"
                f"- **Records:** {result['bigquery_records']:,}\n\n"
                f"## Coverage\n"
                f"- **Coverage:** {result['coverage_percent']}%\n"
                f"- **Gap Before:** {result['gap_before_days']} days\n"
                f"- **Gap After:** {result['gap_after_days']} days\n"
                f"- **Can Backfill:** {'✅ Yes' if result['can_backfill'] else '❌ No'}"
            )

            _LOGGER.info("Export analysis complete: %s", result)

            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": message,
                    "title": "📊 Export Status Analysis",
                    "notification_id": "bigquery_export_analysis"
                }
            )
        else:
            _LOGGER.error("Failed to analyze export status")

    # Handle find data gaps
    async def handle_find_data_gaps(call):
        """Handle the find_data_gaps service call."""
        min_gap_hours = call.data.get('min_gap_hours', 4)
        _LOGGER.info(f"Finding data gaps (min {min_gap_hours} hours)...")

        gaps = await export_service.async_find_data_gaps(min_gap_hours)

        if gaps is not None:
            # Update the gaps sensor
            for entry_id, data in hass.data[DOMAIN].items():
                if "sensors" in data and "gaps" in data["sensors"]:
                    gaps_sensor = data["sensors"]["gaps"]
                    await gaps_sensor.async_update_data(gaps)
                    break
            if len(gaps) == 0:
                message = "✅ No data gaps found! Local database and BigQuery are in sync."
            else:
                message = f"## Found {len(gaps)} Data Gap(s)\n\n"
                for i, gap in enumerate(gaps, 1):
                    message += (
                        f"### Gap {i} ({gap['type']})\n"
                        f"- **Range:** {gap['start']} to {gap['end']}\n"
                        f"- **Days:** {gap['days']}\n"
                        f"- **Estimated Records:** {gap['estimated_records']:,}\n\n"
                    )
                message += "\n💡 Use `bigquery_export.estimate_backfill` to estimate cost/time for filling these gaps."

            _LOGGER.info(f"Found {len(gaps)} gaps")

            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": message,
                    "title": "🔍 Data Gap Analysis",
                    "notification_id": "bigquery_data_gaps"
                }
            )
        else:
            _LOGGER.error("Failed to find data gaps")

    # Handle estimate backfill
    async def handle_estimate_backfill(call):
        """Handle the estimate_backfill service call."""
        start_date = call.data.get('start_date')
        end_date = call.data.get('end_date')

        if not start_date or not end_date:
            _LOGGER.error("start_date and end_date are required")
            return

        _LOGGER.info(f"Estimating backfill from {start_date} to {end_date}...")

        result = await export_service.async_estimate_backfill(start_date, end_date)

        if result:
            message = (
                f"## Backfill Estimate\n"
                f"**Date Range:** {result['start_date']} to {result['end_date']}\n\n"
                f"### Data Volume\n"
                f"- **Total Records:** {result['total_records']:,}\n"
                f"- **Unique Entities:** {result['unique_entities']:,}\n"
                f"- **Days of Data:** {result['days_of_data']}\n\n"
                f"### Processing Time\n"
                f"- **Estimated Time:** {result['estimated_hours']} hours ({result['estimated_minutes']} min)\n"
                f"- **Recommended Chunk Size:** {result['recommended_chunk_days']} days\n\n"
                f"### BigQuery Costs\n"
                f"- **Storage Size:** {result['estimated_size_gb']} GB\n"
                f"- **One-Time Storage Cost:** ${result['estimated_storage_cost']:.4f}\n"
                f"- **Monthly Query Cost (est):** ${result['estimated_query_cost_monthly']:.4f}\n\n"
                f"💡 Run backfill using `bigquery_export.manual_export` with date range."
            )

            _LOGGER.info("Backfill estimate: %s", result)

            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": message,
                    "title": "💰 Backfill Cost Estimate",
                    "notification_id": "bigquery_backfill_estimate"
                }
            )
        else:
            _LOGGER.error("Failed to estimate backfill")

    # Register services
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_EXPORT, handle_manual_export)
    hass.services.async_register(DOMAIN, SERVICE_INCREMENTAL_EXPORT, handle_incremental_export)
    hass.services.async_register(DOMAIN, SERVICE_CHECK_DATABASE_RETENTION, handle_check_database_retention)
    hass.services.async_register(DOMAIN, SERVICE_CHECK_STATISTICS_RETENTION, handle_check_statistics_retention)
    hass.services.async_register(DOMAIN, SERVICE_ANALYZE_EXPORT_STATUS, handle_analyze_export_status)
    hass.services.async_register(DOMAIN, SERVICE_FIND_DATA_GAPS, handle_find_data_gaps)
    hass.services.async_register(DOMAIN, SERVICE_ESTIMATE_BACKFILL, handle_estimate_backfill)

    _LOGGER.debug("Services registered successfully")