"""The Fireboard integration."""
import asyncio
import logging
import json
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
    authentication_success = await api.authenticate()
    if not authentication_success:
        _LOGGER.error("Failed to authenticate with Fireboard API")
        # Continue anyway to show diagnostics, but log the error
        
    async def async_update_data():
        """Fetch data from API."""
        data = {
            "profile": None,
            "devices": [],
            "working_endpoints": {}
        }
        
        try:
            # First get the user profile, as it contains important data
            _LOGGER.debug("Updating data: fetching user profile")
            profile = await api.get_user_profile()
            
            if profile:
                _LOGGER.debug(f"User profile retrieved: {json.dumps(profile)[:100]}...")
                data["profile"] = profile
                
                # Look for devices in the profile if available
                if "userprofile" in profile and "devices" in profile["userprofile"]:
                    devices = profile["userprofile"]["devices"]
                    if devices:
                        _LOGGER.info(f"Found {len(devices)} devices in user profile")
                        data["devices"] = devices
            else:
                _LOGGER.warning("Could not retrieve user profile")
                data["error"] = "Unable to retrieve user profile"
            
            # Discover working API endpoints
            _LOGGER.debug("Discovering working API endpoints")
            working_endpoints = await api._discover_working_api_endpoints()
            data["working_endpoints"] = working_endpoints
            
            # Only try to get devices if we don't already have them from the profile
            if not data["devices"]:
                _LOGGER.debug("Updating data: fetching devices")
                devices = await api.get_devices()
                
                if devices:
                    _LOGGER.info(f"Retrieved {len(devices)} devices")
                    data["devices"] = devices
                else:
                    _LOGGER.warning("No devices found in API response")
                    data["error"] = "No devices found"
            
            # Add extra diagnostics
            data["api_status"] = "connected" if profile and data["devices"] else "limited"
            
            return data
        except Exception as e:
            _LOGGER.error(f"Error updating Fireboard data: {e}")
            # Return partial data if available
            if "profile" in data and data["profile"]:
                _LOGGER.info("Returning partial data (profile only) due to error")
                data["error"] = str(e)
                return data
            else:
                return {
                    "profile": None, 
                    "devices": [], 
                    "error": str(e)
                }

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    # Fetch initial data
    await coordinator.async_refresh()
    
    # Always proceed, even if we couldn't get all data - we'll show diagnostics
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        API: api,
    }

    # Set up all sensor platforms - using updated method
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Log success or partial success
    if coordinator.data and coordinator.data.get("profile"):
        if coordinator.data.get("devices"):
            _LOGGER.info("Fireboard integration set up successfully with devices")
        else:
            _LOGGER.warning("Fireboard integration set up with profile but no devices")
    else:
        _LOGGER.warning("Fireboard integration set up with limited functionality")

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
