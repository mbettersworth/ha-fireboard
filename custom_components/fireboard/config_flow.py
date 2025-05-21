"""Config flow for Fireboard integration."""
import logging
import voluptuous as vol

from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_API_URL,
    DEFAULT_API_URL,
)
from .api import FireboardApiClient

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict):
    """Validate the user input allows us to connect."""
    api_url = data.get(CONF_API_URL, DEFAULT_API_URL)
    api_key = data.get(CONF_API_KEY)
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)
    
    session = async_get_clientsession(hass)
    client = FireboardApiClient(session, api_url, api_key, username, password)
    
    # Try to authenticate
    if not api_key and (not username or not password):
        raise InvalidAuth("You must provide either an API key or username/password")
    
    # Test the API connection
    devices = await client.async_get_devices()
    if devices is None:
        raise CannotConnect("Failed to connect to Fireboard API")
    
    if not devices:
        _LOGGER.warning("Connected to Fireboard API, but no devices found")
    
    # Return info for config entry creation
    return {
        "title": f"Fireboard ({len(devices)} devices)",
        "devices": len(devices),
    }


class ConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for Fireboard."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Build the form with options for API key or username/password
        data_schema = vol.Schema({
            vol.Required(CONF_API_URL, default=DEFAULT_API_URL): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_API_KEY, description="Optional - only needed if provided by Fireboard support"): str,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return FireboardOptionsFlow(config_entry)


class FireboardOptionsFlow(config_entries.OptionsFlow):
    """Handle Fireboard options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "scan_interval",
                    default=self.config_entry.options.get("scan_interval", 60),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
            }),
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""