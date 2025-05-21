"""API client for Fireboard integration."""
import logging
import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)

class FireboardApiClient:
    """API client for Fireboard integration."""

    def __init__(self, hass, api_url, api_key):
        """Initialize the API client."""
        self.hass = hass
        self.api_url = api_url
        self.api_key = api_key
        self.session = None

    async def _get_session(self):
        """Get an aiohttp ClientSession."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _api_request(self, endpoint, method="GET", params=None, data=None):
        """Make a request to the Fireboard API proxy."""
        session = await self._get_session()
        url = f"{self.api_url.rstrip('/')}/api/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            with async_timeout.timeout(10):
                if method == "GET":
                    response = await session.get(url, headers=headers, params=params)
                elif method == "POST":
                    response = await session.post(url, headers=headers, json=data)
                elif method == "PUT":
                    response = await session.put(url, headers=headers, json=data)
                else:
                    _LOGGER.error(f"Unsupported method: {method}")
                    return None

                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error requesting data from {url}: {err}")
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout calling {url}")
        return None

    async def get_devices(self):
        """Get all Fireboard devices."""
        return await self._api_request("devices")

    async def get_device(self, device_id):
        """Get a specific Fireboard device."""
        return await self._api_request(f"device/{device_id}")

    async def get_temperatures(self, device_id):
        """Get temperatures for a device."""
        return await self._api_request(f"device/{device_id}/temps")

    async def get_alerts(self, device_id):
        """Get alerts for a device."""
        return await self._api_request(f"device/{device_id}/alerts")

    async def create_alert(self, device_id, channel_id, min_temp=None, max_temp=None):
        """Create a new alert."""
        data = {
            "device_id": device_id,
            "channel_id": channel_id,
        }
        if min_temp is not None:
            data["min_temp"] = min_temp
        if max_temp is not None:
            data["max_temp"] = max_temp
        
        return await self._api_request("alerts", method="POST", data=data)

    async def delete_alert(self, alert_id):
        """Delete an alert."""
        return await self._api_request(f"alerts/{alert_id}", method="DELETE")
