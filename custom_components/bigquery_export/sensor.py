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
    
    # Add the export status sensor
    async_add_entities([BigQueryExportSensor(coordinator, config_entry)])


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
        self._attr_name = "BigQuery Export Status"
        self._attr_unique_id = f"{config_entry.entry_id}_export_status"
        self._attr_icon = "mdi:export"

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