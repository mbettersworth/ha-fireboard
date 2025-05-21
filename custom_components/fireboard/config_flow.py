"""Config flow for Fireboard integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FireboardApiClient
from .const import DOMAIN, CONF_API_URL, DEFAULT_API_URL

_LOGGER = logging.getLogger(__name__)


class FireboardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fireboard."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                api_url = user_input.get(CONF_API_URL, DEFAULT_API_URL)
                api_key = user_input.get(CONF_API_KEY)
                username = user_input.get(CONF_USERNAME)
                password = user_input.get(CONF_PASSWORD)

                session = async_get_clientsession(self.hass)
                client = FireboardApiClient(session, api_url, api_key, username, password)

                # Check authentication
                if not api_key and (not username or not password):
                    errors["base"] = "invalid_auth"
                else:
                    # Test connection
                    devices = await client.async_get_devices()
                    if devices is None:
                        errors["base"] = "cannot_connect"
                    else:
                        # Success - create entry
                        return self.async_create_entry(
                            title=f"Fireboard ({len(devices)} devices)",
                            data=user_input
                        )

            except Exception:
                _LOGGER.exception("Unexpected error during Fireboard setup")
                errors["base"] = "unknown"

        # Show form
        data_schema = vol.Schema({
            vol.Required(CONF_API_URL, default=DEFAULT_API_URL): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_API_KEY): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )
