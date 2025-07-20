"""BigQuery Export integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SERVICE_MANUAL_EXPORT, SERVICE_INCREMENTAL_EXPORT
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
        
        if success:
            _LOGGER.info("Manual export completed successfully")
        else:
            _LOGGER.error("Manual export failed")
    
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
            return
        
        # Call the service directly since incremental export doesn't need coordinator stats
        success = await export_service.async_incremental_export()
        
        if success:
            _LOGGER.info("Incremental export completed successfully")
            # Trigger coordinator refresh to update sensor
            await coordinator.async_refresh()
        else:
            _LOGGER.error("Incremental export failed")
    
    # Register services
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_EXPORT, handle_manual_export)
    hass.services.async_register(DOMAIN, SERVICE_INCREMENTAL_EXPORT, handle_incremental_export)
    
    _LOGGER.debug("Services registered successfully")