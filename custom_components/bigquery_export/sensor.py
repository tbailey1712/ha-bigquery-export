"""Sensor platform for BigQuery Export."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    ATTR_EXPORT_STATUS,
    ATTR_LAST_EXPORT,
    ATTR_NEXT_EXPORT,
    ATTR_RECORDS_EXPORTED,
    DOMAIN,
)
from .coordinator import BigQueryExportCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    service = hass.data[DOMAIN][config_entry.entry_id]["service"]

    # Create sensor instances
    retention_sensor = BigQueryDatabaseRetentionSensor(coordinator, config_entry, service, hass)
    statistics_sensor = BigQueryStatisticsRetentionSensor(coordinator, config_entry, service, hass)
    coverage_sensor = BigQueryCoverageSensor(coordinator, config_entry, service, hass)
    gaps_sensor = BigQueryDataGapsSensor(coordinator, config_entry, service, hass)

    # Store sensors in hass.data so service calls can update them
    hass.data[DOMAIN][config_entry.entry_id]["sensors"] = {
        "retention": retention_sensor,
        "statistics": statistics_sensor,
        "coverage": coverage_sensor,
        "gaps": gaps_sensor,
    }

    # Add all sensors
    async_add_entities([
        BigQueryExportSensor(coordinator, config_entry),
        retention_sensor,
        statistics_sensor,
        coverage_sensor,
        gaps_sensor,
    ])

    # Auto-populate sensors on startup
    async def _populate_sensors():
        """Populate all diagnostic sensors on startup."""
        try:
            # Check database retention
            retention_data = await service.async_check_database_retention()
            if retention_data:
                await retention_sensor.async_update_data(retention_data)

            # Check statistics retention
            stats_data = await service.async_check_statistics_retention()
            if stats_data:
                await statistics_sensor.async_update_data(stats_data)

            # Analyze coverage
            coverage_data = await service.async_analyze_export_status()
            if coverage_data:
                await coverage_sensor.async_update_data(coverage_data)

            # Find gaps
            gaps_data = await service.async_find_data_gaps(4)
            if gaps_data is not None:
                await gaps_sensor.async_update_data(gaps_data)

        except Exception as err:
            _LOGGER.warning("Error auto-populating sensors on startup: %s", err)

    # Schedule sensor population
    hass.async_create_task(_populate_sensors())


class BigQueryExportSensor(CoordinatorEntity, SensorEntity):
    """Sensor for BigQuery Export status."""

    def __init__(
        self,
        coordinator: BigQueryExportCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = "Export Status"
        self._attr_unique_id = f"{config_entry.entry_id}_export_status"
        self._attr_icon = "mdi:export"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="BigQuery Export",
            manufacturer="Custom",
            model="Data Export Service",
            sw_version="1.2.0",
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return "unknown"
        
        # Show current status if export is in progress
        if self.coordinator.data.get("export_in_progress", False):
            current_status = self.coordinator.data.get("current_status", "exporting")
            return current_status
        
        # Show last export status when idle
        last_status = self.coordinator.data.get("last_export_status")
        if last_status == "success":
            return "success"
        elif last_status == "failed":
            return "failed"
        
        return "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.coordinator.data is None:
            return {}
        
        data = self.coordinator.data
        export_stats = data.get("export_statistics", {})
        export_status = data.get("export_status", {})
        
        
        attributes = {
            ATTR_EXPORT_STATUS: export_status.get("connection_status", "unknown"),
            ATTR_LAST_EXPORT: export_stats.get("last_export_time"),
            ATTR_RECORDS_EXPORTED: export_stats.get("last_export_records", 0),
            "project_id": export_status.get("project_id"),
            "dataset_id": export_status.get("dataset_id"),
            "table_id": export_status.get("table_id"),
        }
        
        # Add current progress info if available
        if data.get("export_in_progress", False):
            current_progress = data.get("current_progress")
            if current_progress:
                attributes["current_progress"] = current_progress
                
        # Add current status
        current_status = data.get("current_status")
        if current_status:
            attributes["current_status"] = current_status
        
        # Add next export time
        next_export = data.get("next_export_time")
        if next_export:
            if isinstance(next_export, datetime):
                attributes[ATTR_NEXT_EXPORT] = next_export.isoformat()
            else:
                attributes[ATTR_NEXT_EXPORT] = next_export
        
        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success


class BigQueryDatabaseRetentionSensor(SensorEntity):
    """Sensor showing local database retention info."""

    _attr_should_poll = False
    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BigQueryExportCoordinator,
        config_entry: ConfigEntry,
        service,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._service = service
        self._hass = hass
        self._attr_name = "Local Database Retention"
        self._attr_unique_id = f"{config_entry.entry_id}_database_retention"
        self._attr_icon = "mdi:database-clock"
        self._attr_native_unit_of_measurement = "days"
        self._attr_device_class = None
        self._retention_data = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="BigQuery Export",
            manufacturer="Custom",
            model="Data Export Service",
            sw_version="1.2.0",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self._retention_data:
            return self._retention_data[2]  # days_of_data
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self._retention_data:
            return {"status": "Click to update", "info": "Run bigquery_export.check_database_retention"}

        return {
            "oldest_date": str(self._retention_data[0]),
            "newest_date": str(self._retention_data[1]),
            "days_of_data": self._retention_data[2],
            "total_records": f"{self._retention_data[3]:,}",
            "info": "Run bigquery_export.check_database_retention to update",
        }

    async def async_update_data(self, data):
        """Update sensor with new data from service call."""
        self._retention_data = data
        self.async_write_ha_state()


class BigQueryCoverageSensor(SensorEntity):
    """Sensor showing export coverage percentage."""

    _attr_should_poll = False
    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BigQueryExportCoordinator,
        config_entry: ConfigEntry,
        service,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._service = service
        self._hass = hass
        self._attr_name = "Export Coverage"
        self._attr_unique_id = f"{config_entry.entry_id}_export_coverage"
        self._attr_icon = "mdi:percent"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = None
        self._coverage_data = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="BigQuery Export",
            manufacturer="Custom",
            model="Data Export Service",
            sw_version="1.2.0",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self._coverage_data:
            return self._coverage_data.get("coverage_percent")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self._coverage_data:
            return {"status": "Click to update", "info": "Run bigquery_export.analyze_export_status"}

        data = self._coverage_data
        return {
            "local_oldest": data.get("local_oldest"),
            "local_newest": data.get("local_newest"),
            "local_days": data.get("local_days"),
            "local_records": f"{data.get('local_records', 0):,}",
            "bigquery_oldest": data.get("bigquery_oldest"),
            "bigquery_newest": data.get("bigquery_newest"),
            "bigquery_days": data.get("bigquery_days"),
            "bigquery_records": f"{data.get('bigquery_records', 0):,}",
            "gap_before_days": data.get("gap_before_days"),
            "gap_after_days": data.get("gap_after_days"),
            "can_backfill": data.get("can_backfill"),
            "info": "Run bigquery_export.analyze_export_status to update",
        }

    async def async_update_data(self, data):
        """Update sensor with new data from service call."""
        self._coverage_data = data
        self.async_write_ha_state()


class BigQueryDataGapsSensor(SensorEntity):
    """Sensor showing data gaps between local and BigQuery."""

    _attr_should_poll = False
    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BigQueryExportCoordinator,
        config_entry: ConfigEntry,
        service,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._service = service
        self._hass = hass
        self._attr_name = "Data Gaps"
        self._attr_unique_id = f"{config_entry.entry_id}_data_gaps"
        self._attr_icon = "mdi:chart-timeline-variant"
        self._attr_device_class = None
        self._gaps_data = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="BigQuery Export",
            manufacturer="Custom",
            model="Data Export Service",
            sw_version="1.2.0",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self._gaps_data is not None:
            return len(self._gaps_data)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self._gaps_data is None:
            return {"status": "Click to update", "info": "Run bigquery_export.find_data_gaps"}

        if len(self._gaps_data) == 0:
            return {
                "status": "No gaps found",
                "info": "Local database and BigQuery are in sync",
            }

        # Format gaps for display
        gaps_formatted = []
        total_missing_days = 0
        total_missing_records = 0

        for i, gap in enumerate(self._gaps_data, 1):
            gaps_formatted.append({
                "gap_number": i,
                "type": gap.get("type"),
                "start_date": gap.get("start"),
                "end_date": gap.get("end"),
                "days": gap.get("days"),
                "estimated_records": f"{gap.get('estimated_records', 0):,}",
            })
            total_missing_days += gap.get("days", 0)
            total_missing_records += gap.get("estimated_records", 0)

        return {
            "gaps": gaps_formatted,
            "total_gaps": len(self._gaps_data),
            "total_missing_days": total_missing_days,
            "total_missing_records": f"{total_missing_records:,}",
            "info": "Run bigquery_export.find_data_gaps to update",
        }

    async def async_update_data(self, data):
        """Update sensor with new data from service call."""
        self._gaps_data = data
        self.async_write_ha_state()


class BigQueryStatisticsRetentionSensor(SensorEntity):
    """Sensor showing statistics table retention info."""

    _attr_should_poll = False
    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BigQueryExportCoordinator,
        config_entry: ConfigEntry,
        service,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._service = service
        self._hass = hass
        self._attr_name = "Statistics Table Retention"
        self._attr_unique_id = f"{config_entry.entry_id}_statistics_retention"
        self._attr_icon = "mdi:chart-line"
        self._attr_native_unit_of_measurement = "days"
        self._attr_device_class = None
        self._statistics_data = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="BigQuery Export",
            manufacturer="Custom",
            model="Data Export Service",
            sw_version="1.2.0",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self._statistics_data:
            return self._statistics_data[2]  # days_of_data
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self._statistics_data:
            return {
                "status": "Loading...",
                "info": "Statistics table stores aggregated long-term data"
            }

        return {
            "oldest_date": str(self._statistics_data[0]),
            "newest_date": str(self._statistics_data[1]),
            "days_of_data": self._statistics_data[2],
            "total_records": f"{self._statistics_data[3]:,}",
            "table_type": "statistics",
            "info": "This is likely what you see in History graphs!",
        }

    async def async_update_data(self, data):
        """Update sensor with new data from service call."""
        self._statistics_data = data
        self.async_write_ha_state()