"""The Fireboard integration."""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    COORDINATOR,
    API,
    DEFAULT_SCAN_INTERVAL
)
from .api import FireboardApiClient

_LOGGER = logging.getLogger(__name__)

# Remove the manual configuration schema as we're using config entries
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Fireboard component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Fireboard from a config entry."""
    username = entry.data["username"]
    password = entry.data["password"]
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    api = FireboardApiClient(hass, username=username, password=password, session=session)
    
    # Authenticate with the Fireboard API
    if not await api.authenticate():
        _LOGGER.error("Failed to authenticate with Fireboard API")
        return False

    async def async_update_data():
        """Fetch data from API."""
        try:
            # First get the user profile, as it contains important data
            profile = await api.get_user_profile()
            if not profile:
                _LOGGER.warning("Could not retrieve user profile")
                return None
                
            # Then try to get device data
            devices = await api.get_devices()
            
            # Combine user profile and device data
            return {
                "profile": profile,
                "devices": devices or []
            }
        except Exception as e:
            _LOGGER.error(f"Error updating Fireboard data: {e}")
            return None

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    # Fetch initial data
    await coordinator.async_refresh()
    
    # Verify that we could get some data
    if coordinator.data is None:
        _LOGGER.error("Unable to fetch data from Fireboard API")
        return False

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        API: api,
    }

    # Set up all sensor platforms
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


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

    return unload_ok
