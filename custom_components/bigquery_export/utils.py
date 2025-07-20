"""Utility functions for BigQuery Export integration."""
import json
import logging
import os
import re
import yaml
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _resolve_secret(hass: HomeAssistant, value: str) -> str:
    """Resolve !secret references to actual values."""
    if not value.startswith("!secret "):
        return value
    
    secret_name = value[8:].strip()  # Remove "!secret " prefix
    
    try:
        # Load secrets.yaml file
        secrets_path = os.path.join(hass.config.config_dir, "secrets.yaml")
        if not os.path.exists(secrets_path):
            raise RuntimeError("secrets.yaml not found. Please create it with your service account key.")
        
        with open(secrets_path, "r", encoding="utf-8") as secrets_file:
            secrets = yaml.safe_load(secrets_file) or {}
        
        if secret_name not in secrets:
            raise RuntimeError(f"Secret '{secret_name}' not found in secrets.yaml")
        
        secret_value = secrets[secret_name]
        
        # Handle multiline secrets (service account keys are typically multiline)
        if isinstance(secret_value, str):
            return secret_value
        else:
            # If it's a dict (parsed JSON), convert back to JSON string
            return json.dumps(secret_value)
            
    except yaml.YAMLError as err:
        raise RuntimeError(f"Error parsing secrets.yaml: {err}") from err
    except Exception as err:
        raise RuntimeError(f"Error loading secret '{secret_name}': {err}") from err


def is_valid_project_id(project_id: str) -> bool:
    """Validate Google Cloud project ID format.
    
    Project IDs must be 6-30 characters long, containing only lowercase letters,
    numbers, and hyphens. They cannot start or end with a hyphen.
    """
    if not project_id or not isinstance(project_id, str):
        return False
    
    # Check length
    if len(project_id) < 6 or len(project_id) > 30:
        return False
    
    # Check format: lowercase letters, numbers, hyphens, not starting/ending with hyphen
    pattern = r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$'
    return bool(re.match(pattern, project_id))


def is_valid_dataset_id(dataset_id: str) -> bool:
    """Validate BigQuery dataset ID format.
    
    Dataset IDs must be 1-1024 characters long, containing only letters,
    numbers, and underscores.
    """
    if not dataset_id or not isinstance(dataset_id, str):
        return False
    
    # Check length
    if len(dataset_id) < 1 or len(dataset_id) > 1024:
        return False
    
    # Check format: letters, numbers, underscores only
    pattern = r'^[a-zA-Z0-9_]+$'
    return bool(re.match(pattern, dataset_id))


def is_valid_table_id(table_id: str) -> bool:
    """Validate BigQuery table ID format.
    
    Table IDs must be 1-1024 characters long, containing only letters,
    numbers, and underscores.
    """
    if not table_id or not isinstance(table_id, str):
        return False
    
    # Check length
    if len(table_id) < 1 or len(table_id) > 1024:
        return False
    
    # Check format: letters, numbers, underscores only
    pattern = r'^[a-zA-Z0-9_]+$'
    return bool(re.match(pattern, table_id))


def validate_bigquery_identifiers(project_id: str, dataset_id: str, table_id: str) -> None:
    """Validate BigQuery project, dataset, and table identifiers.
    
    Raises:
        ValueError: If any identifier is invalid.
    """
    if not is_valid_project_id(project_id):
        raise ValueError(f"Invalid project ID: {project_id}")
    
    if not is_valid_dataset_id(dataset_id):
        raise ValueError(f"Invalid dataset ID: {dataset_id}")
    
    if not is_valid_table_id(table_id):
        raise ValueError(f"Invalid table ID: {table_id}")


def should_export_entity(entity_id: str, allowed_entities: List[str]) -> bool:
    """Determine if entity should be exported based on allowlist.
    
    Args:
        entity_id: The entity ID to check
        allowed_entities: List of allowed entity patterns (supports glob patterns)
        
    Returns:
        True if entity should be exported, False otherwise
    """
    import fnmatch
    
    if not allowed_entities:
        return False
    
    return any(fnmatch.fnmatch(entity_id, pattern) for pattern in allowed_entities)


def sanitize_attributes(
    entity_id: str, 
    attributes: Dict[str, Any], 
    denied_attributes: Dict[str, List[str]]
) -> Dict[str, Any]:
    """Remove denied attributes from an entity's attribute dictionary.
    
    Args:
        entity_id: The entity ID
        attributes: The entity's attributes dictionary
        denied_attributes: Dict mapping entity patterns to lists of denied attributes
        
    Returns:
        Sanitized attributes dictionary
    """
    import fnmatch
    
    if not attributes or not denied_attributes:
        return attributes
    
    sanitized = attributes.copy()
    
    # Find matching patterns for this entity
    for pattern, denied_attrs in denied_attributes.items():
        if fnmatch.fnmatch(entity_id, pattern):
            # Remove denied attributes
            for attr in denied_attrs:
                sanitized.pop(attr, None)
    
    return sanitized


def validate_service_account_key(service_account_key: str) -> Dict[str, Any]:
    """Validate and parse service account key JSON.
    
    Args:
        service_account_key: JSON string of the service account key
        
    Returns:
        Parsed service account key dictionary
        
    Raises:
        ValueError: If the key is invalid
    """
    try:
        key_data = json.loads(service_account_key)
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON in service account key: {err}") from err
    
    # Required fields in a service account key
    required_fields = [
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri"
    ]
    
    for field in required_fields:
        if field not in key_data:
            raise ValueError(f"Missing required field '{field}' in service account key")
    
    # Validate type
    if key_data["type"] != "service_account":
        raise ValueError(f"Invalid key type: {key_data['type']}. Expected 'service_account'")
    
    # Validate email format
    client_email = key_data["client_email"]
    if not re.match(r'^[^@]+@[^@]+\.iam\.gserviceaccount\.com$', client_email):
        raise ValueError(f"Invalid service account email format: {client_email}")
    
    # Validate project ID
    if not is_valid_project_id(key_data["project_id"]):
        raise ValueError(f"Invalid project ID in service account key: {key_data['project_id']}")
    
    return key_data


def log_security_event(
    hass: HomeAssistant,
    event_type: str,
    details: Dict[str, Any],
    level: str = "info"
) -> None:
    """Log security-related events with structured format.
    
    Args:
        hass: Home Assistant instance
        event_type: Type of security event (e.g., "auth_success", "auth_failure")
        details: Event details (user_id, entity_id, etc.)
        level: Log level ("debug", "info", "warning", "error")
    """
    # Create structured log entry
    log_entry = {
        "event_type": event_type,
        "component": "bigquery_export",
        "timestamp": hass.loop.time(),
        **details
    }
    
    # Log at appropriate level
    log_func = getattr(_LOGGER, level, _LOGGER.info)
    log_func("Security event: %s", json.dumps(log_entry, default=str))