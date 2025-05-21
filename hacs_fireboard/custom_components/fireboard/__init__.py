"""The Fireboard integration."""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    CONF_API_KEY,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_API_URL,
    COORDINATOR,
    API
)
from .api import FireboardApiClient
from .service import async_setup_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config):
    """Set up the Fireboard component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Fireboard from a config entry."""
    # Get configuration from the entry
    api_key = entry.data.get(CONF_API_KEY)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    api_url = entry.data.get(CONF_API_URL, "https://fireboard.io/api/v1")

    # Create API client
    session = async_get_clientsession(hass)
    api = FireboardApiClient(session, api_url, api_key, username, password)

    # Verify API connection
    devices = await api.async_get_devices()
    if devices is None:
        _LOGGER.error("Failed to connect to Fireboard API")
        return False

    # Create update coordinator
    async def async_update_data():
        """Fetch data from API."""
        try:
            # Get all devices
            devices = await api.async_get_devices()
            
            if not devices:
                return {}
                
            # Get latest temperature data for each device
            for device in devices:
                device_id = device.get("id")
                temps = await api.async_get_temps(device_id)
                if temps:
                    device["temps"] = temps
                else:
                    device["temps"] = []
                    
                # Get alert configuration
                alerts = await api.async_get_alerts(device_id)
                if alerts:
                    device["alerts"] = alerts
                else:
                    device["alerts"] = []
                    
            return devices
        except Exception as err:
            _LOGGER.error("Error updating Fireboard data: %s", err)
            raise

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store API client and coordinator in HASS data
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        API: api,
    }

    # Set up platforms
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    
    # Set up services
    if len(hass.data[DOMAIN]) == 1:
        await async_setup_services(hass)

    # Register entity services when config entry is loaded
    entry.async_on_unload(
        entry.add_update_listener(async_update_listener)
    )

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Unregister services when the last entry is unloaded
        if not hass.data[DOMAIN]:
            await async_unregister_services(hass)

    return unload_ok