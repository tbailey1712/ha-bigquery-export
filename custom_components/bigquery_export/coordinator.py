"""Data update coordinator for BigQuery Export."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_LAST_EXPORT_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)




class BigQueryExportCoordinator(DataUpdateCoordinator):
    """Coordinator for BigQuery Export."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # Disable automatic updates (manual only)
        )
        self.entry = entry
        self.config = entry.data.copy()
        self._export_in_progress = False
        self._last_export_status = None
        self._current_status = "idle"
        self._current_progress = None
        self._last_run_finish_time = None  # For rate limiting
        self._export_statistics = {
            "last_export_time": None,
            "last_export_records": 0,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data."""
        try:
            # Get the export service
            export_service = self.hass.data[DOMAIN][self.entry.entry_id]["service"]
            
            # Get current export status (no automatic exports)
            export_status = export_service.get_export_status()
            
            # Update our data
            data = {
                "export_status": export_status,
                "export_statistics": self._export_statistics,
                "export_in_progress": self._export_in_progress,
                "last_export_status": self._last_export_status,
                "current_status": self._current_status,
                "current_progress": self._current_progress,
            }
            
            return data
            
        except Exception as err:
            _LOGGER.error("Error updating coordinator data: %s", err)
            raise UpdateFailed(f"Error updating coordinator data: {err}") from err


    async def async_manual_export(
        self, 
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        days_back: int = 30
    ) -> bool:
        """Trigger a manual export."""
        _LOGGER.info("Manual export started: %d days", days_back)
        
        if self._export_in_progress:
            _LOGGER.warning("Export already in progress")
            return False
        
        # Rate limiting - prevent rapid sequential runs
        if self._last_run_finish_time:
            time_since_last = dt_util.utcnow() - self._last_run_finish_time
            if time_since_last < timedelta(seconds=60):
                _LOGGER.warning(
                    "Export called too soon after the last run. Please wait %d seconds.",
                    60 - int(time_since_last.total_seconds())
                )
                return False
        
        self._export_in_progress = True
        self._current_status = "initializing"
        self._current_progress = "Starting export process..."
        
        try:
            # Get the export service
            export_service = self.hass.data[DOMAIN][self.entry.entry_id]["service"]
            
            # Perform the export with parameters
            success = await export_service.async_manual_export(
                start_time=start_time,
                end_time=end_time,
                days_back=days_back,
                status_callback=self.update_export_status
            )
            
            if success:
                self._last_export_status = "success"
                self._export_statistics["last_export_time"] = dt_util.utcnow().isoformat()
                # Try to get record count from the export service
                try:
                    if hasattr(export_service, '_last_export_count'):
                        self._export_statistics["last_export_records"] = export_service._last_export_count
                except Exception as e:
                    _LOGGER.warning("Could not get export count: %s", e)
                
                _LOGGER.info("Manual export completed successfully - records: %s", 
                           self._export_statistics.get("last_export_records", "unknown"))
            else:
                self._last_export_status = "failed"
                _LOGGER.error("Manual export failed")
            
            # Trigger a data update
            await self.async_refresh()
            
            return success
            
        except Exception as err:
            self._last_export_status = "failed"
            _LOGGER.error("Error during manual export: %s", err, exc_info=True)
            return False
            
        finally:
            self._export_in_progress = False
            self._last_run_finish_time = dt_util.utcnow()  # Record finish time for rate limiting
            self._current_status = "idle"
            self._current_progress = None

    def update_export_status(self, status: str, progress: str = None) -> None:
        """Update the current export status and progress."""
        self._current_status = status
        self._current_progress = progress

        # Log progress updates at INFO level for visibility
        if progress:
            _LOGGER.info("Export status: %s - %s", status, progress)
        else:
            _LOGGER.info("Export status: %s", status)

        # Trigger immediate data refresh to update sensor
        # Use call_soon_threadsafe for thread safety when called from executor
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(self.async_refresh())
        )

    def get_export_statistics(self) -> dict[str, Any]:
        """Get export statistics."""
        return self._export_statistics.copy()

    def is_export_in_progress(self) -> bool:
        """Check if an export is currently in progress."""
        return self._export_in_progress

    async def async_test_connection(self) -> bool:
        """Test the BigQuery connection."""
        try:
            export_service = self.hass.data[DOMAIN][self.entry.entry_id]["service"]
            return await export_service.async_test_connection()
        except Exception as err:
            _LOGGER.error("Error testing connection: %s", err)
            return False