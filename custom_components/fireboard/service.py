"""Service handlers for Fireboard integration."""
import logging
import voluptuous as vol
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    COORDINATOR,
    API,
    ATTR_DEVICE_ID,
    ATTR_CHANNEL_ID,
    ATTR_MIN_TEMP,
    ATTR_MAX_TEMP,
    ATTR_ALERT_ID,
)

_LOGGER = logging.getLogger(__name__)

# Schema for create_alert service
CREATE_ALERT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_CHANNEL_ID): cv.string,
        vol.Optional(ATTR_MIN_TEMP): vol.Coerce(float),
        vol.Optional(ATTR_MAX_TEMP): vol.Coerce(float),
    }
)

# Schema for delete_alert service
DELETE_ALERT_SCHEMA = vol.Schema({vol.Required(ATTR_ALERT_ID): cv.string})

# Schema for refresh_data service
REFRESH_DATA_SCHEMA = vol.Schema({vol.Optional(ATTR_DEVICE_ID): cv.string})


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Fireboard services."""
    
    async def handle_create_alert(call: ServiceCall) -> None:
        """Handle create_alert service calls."""
        device_id = call.data[ATTR_DEVICE_ID]
        channel_id = call.data[ATTR_CHANNEL_ID]
        min_temp = call.data.get(ATTR_MIN_TEMP)
        max_temp = call.data.get(ATTR_MAX_TEMP)
        
        # Find the config entry for this device
        for entry_id, data in hass.data[DOMAIN].items():
            api = data[API]
            
            try:
                result = await api.async_create_alert(
                    device_id, channel_id, min_temp=min_temp, max_temp=max_temp
                )
                
                if result:
                    _LOGGER.info(
                        "Created alert for device %s, channel %s: min=%s, max=%s",
                        device_id,
                        channel_id,
                        min_temp,
                        max_temp,
                    )
                    
                    # Refresh coordinator data
                    await hass.data[DOMAIN][entry_id][COORDINATOR].async_refresh()
                    return
                
                _LOGGER.error("Failed to create alert")
            except Exception as err:
                _LOGGER.error("Error creating alert: %s", err)
        
        _LOGGER.error("No API connection found for device %s", device_id)
    
    async def handle_delete_alert(call: ServiceCall) -> None:
        """Handle delete_alert service calls."""
        alert_id = call.data[ATTR_ALERT_ID]
        
        # Try with each API instance
        for entry_id, data in hass.data[DOMAIN].items():
            api = data[API]
            
            try:
                result = await api.async_delete_alert(alert_id)
                
                if result:
                    _LOGGER.info("Deleted alert %s", alert_id)
                    
                    # Refresh coordinator data
                    await hass.data[DOMAIN][entry_id][COORDINATOR].async_refresh()
                    return
            except Exception as err:
                _LOGGER.error("Error deleting alert: %s", err)
        
        _LOGGER.error("Failed to delete alert %s", alert_id)
    
    async def handle_refresh_data(call: ServiceCall) -> None:
        """Handle refresh_data service calls."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        
        # Refresh all coordinators
        for entry_id, data in hass.data[DOMAIN].items():
            coordinator = data[COORDINATOR]
            await coordinator.async_refresh()
        
        _LOGGER.info(
            "Refreshed Fireboard data%s",
            f" for device {device_id}" if device_id else "",
        )
    
    # Register services
    hass.services.async_register(
        DOMAIN, "create_alert", handle_create_alert, schema=CREATE_ALERT_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "delete_alert", handle_delete_alert, schema=DELETE_ALERT_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "refresh_data", handle_refresh_data, schema=REFRESH_DATA_SCHEMA
    )


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister Fireboard services."""
    if hass.services.has_service(DOMAIN, "create_alert"):
        hass.services.async_remove(DOMAIN, "create_alert")
    
    if hass.services.has_service(DOMAIN, "delete_alert"):
        hass.services.async_remove(DOMAIN, "delete_alert")
    
    if hass.services.has_service(DOMAIN, "refresh_data"):
        hass.services.async_remove(DOMAIN, "refresh_data")