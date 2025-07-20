"""Config flow for BigQuery Export integration."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import voluptuous as vol
import yaml

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import load_yaml

from .const import (
    CONF_ALLOWED_ENTITIES,
    CONF_DATASET_ID,
    CONF_DENIED_ATTRIBUTES,
    CONF_FILTERING_MODE,
    CONF_PROJECT_ID,
    CONF_SERVICE_ACCOUNT_KEY,
    CONF_TABLE_ID,
    DEFAULT_TABLE_ID,
    DOMAIN,
    FILTERING_MODE_EXCLUDE,
    FILTERING_MODE_INCLUDE,
)
from .utils import _resolve_secret

_LOGGER = logging.getLogger(__name__)



STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PROJECT_ID): str,
        vol.Required(CONF_DATASET_ID): str,
        vol.Optional(CONF_TABLE_ID, default=DEFAULT_TABLE_ID): str,
        vol.Required(CONF_SERVICE_ACCOUNT_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect to BigQuery."""
    
    def _validate():
        try:
            # Resolve secret reference if needed
            service_account_key = _resolve_secret(hass, data[CONF_SERVICE_ACCOUNT_KEY])
            
            # Parse the service account key
            service_account_info = json.loads(service_account_key)
            
            # Basic validation - check if it looks like a service account key
            required_fields = ["type", "project_id", "private_key_id", "private_key", "client_email"]
            for field in required_fields:
                if field not in service_account_info:
                    raise InvalidServiceAccountKey(f"Missing required field: {field}")
            
            if service_account_info.get("type") != "service_account":
                raise InvalidServiceAccountKey("Not a service account key")
            
            # Try to create BigQuery client and test connection
            try:
                from google.cloud import bigquery
                from google.oauth2 import service_account
                from google.auth import exceptions as auth_exceptions
                
                # Create credentials
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info
                )
                
                # Initialize BigQuery client
                client = bigquery.Client(
                    credentials=credentials,
                    project=data[CONF_PROJECT_ID]
                )
                
                # Test connection by listing datasets
                datasets = list(client.list_datasets(max_results=1))
                
                # Check if the specified dataset exists
                dataset_id = data[CONF_DATASET_ID]
                dataset_exists = any(dataset.dataset_id == dataset_id for dataset in client.list_datasets())
                
                if not dataset_exists:
                    # Try to create the dataset
                    dataset = bigquery.Dataset(f"{data[CONF_PROJECT_ID]}.{dataset_id}")
                    dataset.location = "US"  # Default location
                    client.create_dataset(dataset)
                    _LOGGER.info("Created dataset: %s", dataset_id)
                
                _LOGGER.info("BigQuery connection validated successfully")
                
            except auth_exceptions.GoogleAuthError as err:
                raise InvalidAuth from err
            except Exception as err:
                _LOGGER.error("BigQuery connection test failed: %s", err)
                raise CannotConnect from err
            
            return {"title": f"BigQuery Export ({data[CONF_PROJECT_ID]})"}
            
        except json.JSONDecodeError as err:
            raise InvalidServiceAccountKey("Invalid JSON format") from err
        except (InvalidServiceAccountKey, InvalidAuth, CannotConnect):
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error validating BigQuery connection")
            raise CannotConnect from err
    
    return await hass.async_add_executor_job(_validate)


class BigQueryExportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BigQuery Export."""

    VERSION = 1
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidServiceAccountKey:
                errors["base"] = "invalid_service_account_key"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to BigQuery."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidServiceAccountKey(HomeAssistantError):
    """Error to indicate there is an invalid service account key."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for BigQuery Export."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Process string inputs into proper data structures
            processed_input = {}
            
            # Process allowed entities (from entity_filters field)
            # Handle multiple separator types: newlines, commas, semicolons, spaces
            allowed_str = user_input.get("entity_filters", "").strip()
            if allowed_str:
                # First try newlines (preferred)
                patterns = [line.strip() for line in allowed_str.split("\n") if line.strip()]
                
                # If we only got one pattern, try other separators
                if len(patterns) == 1:
                    single_pattern = patterns[0]
                    # Try comma separation
                    if "," in single_pattern:
                        patterns = [p.strip() for p in single_pattern.split(",") if p.strip()]
                    # Try semicolon separation
                    elif ";" in single_pattern:
                        patterns = [p.strip() for p in single_pattern.split(";") if p.strip()]
                    # Try space separation (be careful with this - only if no wildcards in middle)
                    elif " " in single_pattern and "*" not in single_pattern.replace("*", ""):
                        # Only split on spaces if there are no wildcards that might be part of pattern
                        potential_patterns = [p.strip() for p in single_pattern.split() if p.strip()]
                        # Validate that these look like entity patterns
                        if all("." in p or "*" in p for p in potential_patterns):
                            patterns = potential_patterns
                
                processed_input[CONF_ALLOWED_ENTITIES] = patterns
            else:
                processed_input[CONF_ALLOWED_ENTITIES] = []
            
            # Process denied attributes
            denied_str = user_input.get(CONF_DENIED_ATTRIBUTES, "").strip()
            denied_dict = {}
            if denied_str:
                for line in denied_str.split("\n"):
                    line = line.strip()
                    if line and ":" in line:
                        pattern, attr = line.split(":", 1)
                        pattern = pattern.strip()
                        attr = attr.strip()
                        if pattern not in denied_dict:
                            denied_dict[pattern] = []
                        denied_dict[pattern].append(attr)
            processed_input[CONF_DENIED_ATTRIBUTES] = denied_dict
            
            # Process filtering mode
            processed_input[CONF_FILTERING_MODE] = user_input.get(CONF_FILTERING_MODE, FILTERING_MODE_EXCLUDE)
            
            return self.async_create_entry(title="", data=processed_input)

        # Get current options
        current_allowed = self.config_entry.options.get(CONF_ALLOWED_ENTITIES, [])
        current_denied = self.config_entry.options.get(CONF_DENIED_ATTRIBUTES, {})
        current_mode = self.config_entry.options.get(CONF_FILTERING_MODE, FILTERING_MODE_EXCLUDE)
        
        # Convert lists/dicts to strings for the form
        allowed_str = "\n".join(current_allowed) if current_allowed else ""
        denied_str = ""
        if current_denied:
            denied_lines = []
            for pattern, attrs in current_denied.items():
                if isinstance(attrs, list):
                    for attr in attrs:
                        denied_lines.append(f"{pattern}:{attr}")
                else:
                    denied_lines.append(f"{pattern}:{attrs}")
            denied_str = "\n".join(denied_lines)

        schema = vol.Schema({
            vol.Required(
                CONF_FILTERING_MODE,
                default=current_mode
            ): vol.In({
                FILTERING_MODE_EXCLUDE: "Export All (with exclusions) - Current behavior",
                FILTERING_MODE_INCLUDE: "Include Only - Secure allowlist mode"
            }),
            vol.Optional(
                "entity_filters", 
                default=allowed_str,
                description={
                    "suggested_value": allowed_str
                }
            ): str,
            vol.Optional(
                CONF_DENIED_ATTRIBUTES,
                default=denied_str,
                description={
                    "suggested_value": denied_str
                }
            ): str,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "mode_help": "Export All: Uses existing filtering logic (what you have now). Include Only: Secure mode where only specified entities are exported.",
                "entity_help": "Multiple formats supported: newlines (preferred), commas, semicolons. For 'Export All': patterns to EXCLUDE. For 'Include Only': patterns to INCLUDE. Examples:\nsensor.temperature_*, binary_sensor.door_*, light.living_room",
                "denied_help": "Attributes to remove from exported data. Format: pattern:attribute (newlines or commas). Examples:\ndevice_tracker.*:latitude, device_tracker.*:longitude, person.*:address"
            }
        )