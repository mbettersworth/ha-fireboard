"""Config flow for Fireboard integration."""
import logging
import re
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .api import FireboardApiClient

_LOGGER = logging.getLogger(__name__)

# Simple email validation regex - not perfect but avoids blocking calls
EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect."""
    username = data["username"]
    password = data["password"]
    
    # Validate that username looks like an email address
    # Using simple regex to avoid blocking calls from email_validator library
    if not EMAIL_REGEX.match(username):
        raise InvalidAuth("Username must be a valid email address")

    # Try to authenticate with Fireboard
    session = async_get_clientsession(hass)
    client = FireboardApiClient(hass, username=username, password=password, session=session)
    
    _LOGGER.debug(f"Authenticating with Fireboard API using username: {username}")
    if not await client.authenticate():
        _LOGGER.error(f"Authentication failed for user: {username}")
        raise InvalidAuth("Invalid username or password")
    
    # Get user profile to verify connection
    _LOGGER.debug("Getting user profile to verify connection")
    profile = await client.get_user_profile()
    if not profile:
        _LOGGER.error("Unable to retrieve user profile")
        raise CannotConnect("Unable to retrieve user profile")
    
    _LOGGER.debug(f"Successfully retrieved user profile, ID: {profile.get('id')}")
    
    # Try to get devices - we continue even if no devices found
    _LOGGER.debug("Attempting to retrieve devices")
    devices = await client.get_devices()
    device_count = len(devices) if devices else 0
    
    if device_count > 0:
        _LOGGER.info(f"Found {device_count} devices")
    else:
        _LOGGER.warning("No devices found, but authentication was successful")
    
    # Return info to store in the config entry
    return {
        "title": f"Fireboard ({username})",
        "username": username,
        "password": password,
        "user_id": profile.get("id", "")
    }


class FireboardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fireboard."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=info)
            except CannotConnect as e:
                _LOGGER.error(f"Cannot connect: {e}")
                errors["base"] = "cannot_connect"
            except InvalidAuth as e:
                _LOGGER.error(f"Invalid auth: {e}")
                errors["base"] = "invalid_auth"
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception(f"Unexpected exception: {e}")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Fireboard."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                "scan_interval",
                default=self.config_entry.options.get(
                    "scan_interval", DEFAULT_SCAN_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=30, max=300))
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate authentication failed."""
