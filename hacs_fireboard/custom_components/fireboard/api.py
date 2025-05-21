"""API client for Fireboard integration."""
import logging
from typing import Dict, List, Optional, Any

import aiohttp

from .const import (
    CONF_API_KEY,
    CONF_USERNAME,
    CONF_PASSWORD,
)

_LOGGER = logging.getLogger(__name__)


class FireboardApiClient:
    """API client for Fireboard."""

    def __init__(
        self, 
        session: aiohttp.ClientSession, 
        api_url: str, 
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """Initialize the API client."""
        self._session = session
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self.token = None
        self.headers = {"Content-Type": "application/json"}
        
        # Set API key in headers if provided
        if self.api_key:
            self.headers["X-API-KEY"] = self.api_key

    async def _authenticate(self) -> bool:
        """Authenticate with username and password."""
        if not self.username or not self.password:
            return False

        auth_url = f"{self.api_url}/rest-auth/login/"
        try:
            async with self._session.post(
                auth_url,
                json={"username": self.username, "password": self.password},
                headers=self.headers,
            ) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Authentication failed: %s", await response.text()
                    )
                    return False
                    
                data = await response.json()
                self.token = data.get("key")  # Updated to use "key" instead of "token"
                if self.token:
                    self.headers["Authorization"] = f"Token {self.token}"
                    return True
                return False
        except (aiohttp.ClientError, aiohttp.ClientResponseError) as err:
            _LOGGER.error("Error authenticating to Fireboard API: %s", err)
            return False

    async def _api_request(
        self, 
        endpoint: str, 
        method: str = "GET", 
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make a request to the Fireboard API."""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        # Authenticate if needed and no API key
        if not self.api_key and not self.token:
            if not await self._authenticate():
                _LOGGER.error("Authentication required but failed")
                return None

        for _ in range(2):  # Try twice (second attempt after re-auth)
            try:
                if method == "GET":
                    async with self._session.get(
                        url, headers=self.headers, params=params
                    ) as response:
                        if response.status == 401 and self.username and self.password:
                            # Token expired, try to re-authenticate
                            if await self._authenticate():
                                continue  # Retry the request
                            return None
                            
                        response.raise_for_status()
                        return await response.json()
                        
                elif method == "POST":
                    async with self._session.post(
                        url, headers=self.headers, json=data
                    ) as response:
                        if response.status == 401 and self.username and self.password:
                            # Token expired, try to re-authenticate
                            if await self._authenticate():
                                continue  # Retry the request
                            return None
                            
                        response.raise_for_status()
                        return await response.json()
                        
                elif method == "PUT":
                    async with self._session.put(
                        url, headers=self.headers, json=data
                    ) as response:
                        if response.status == 401 and self.username and self.password:
                            # Token expired, try to re-authenticate
                            if await self._authenticate():
                                continue  # Retry the request
                            return None
                            
                        response.raise_for_status()
                        return await response.json()
                        
                elif method == "DELETE":
                    async with self._session.delete(
                        url, headers=self.headers
                    ) as response:
                        if response.status == 401 and self.username and self.password:
                            # Token expired, try to re-authenticate
                            if await self._authenticate():
                                continue  # Retry the request
                            return None
                            
                        response.raise_for_status()
                        if response.status == 204:  # No content
                            return {}
                        return await response.json()
                
            except aiohttp.ClientResponseError as err:
                _LOGGER.error("API request error: %s, URL: %s", err, url)
                return None
            except aiohttp.ClientError as err:
                _LOGGER.error("Request error: %s, URL: %s", err, url)
                return None
            
            # If we got here, the request was successful
            break
            
        return None  # Request failed after retry

    async def async_get_devices(self) -> Optional[List[Dict[str, Any]]]:
        """Get all Fireboard devices."""
        return await self._api_request("v1/devices/")

    async def async_get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific device."""
        return await self._api_request(f"v1/devices/{device_id}/")

    async def async_get_temps(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get temperatures for a device."""
        return await self._api_request(f"v1/devices/{device_id}/temps/")

    async def async_get_alerts(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get alerts for a device."""
        return await self._api_request(f"v1/devices/{device_id}/alerts/")

    async def async_create_alert(
        self, 
        device_id: str, 
        channel_id: str, 
        min_temp: Optional[float] = None, 
        max_temp: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new temperature alert."""
        data = {"device": device_id, "channel": channel_id}
        
        if min_temp is not None:
            data["min"] = min_temp
        if max_temp is not None:
            data["max"] = max_temp
            
        return await self._api_request("v1/alerts/", method="POST", data=data)

    async def async_update_alert(
        self,
        alert_id: str,
        min_temp: Optional[float] = None,
        max_temp: Optional[float] = None,
        enabled: Optional[bool] = None
    ) -> Optional[Dict[str, Any]]:
        """Update an existing alert."""
        data = {}
        
        if min_temp is not None:
            data["min"] = min_temp
        if max_temp is not None:
            data["max"] = max_temp
        if enabled is not None:
            data["enabled"] = enabled
            
        return await self._api_request(f"v1/alerts/{alert_id}/", method="PUT", data=data)

    async def async_delete_alert(self, alert_id: str) -> bool:
        """Delete an alert."""
        result = await self._api_request(f"v1/alerts/{alert_id}/", method="DELETE")
        return result is not None

    async def async_get_sessions(
        self, 
        device_id: Optional[str] = None, 
        limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """Get recent cooking sessions."""
        params = {"limit": limit}
        
        if device_id:
            return await self._api_request(f"v1/devices/{device_id}/sessions/", params=params)
        else:
            return await self._api_request("v1/sessions/", params=params)

    async def async_get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific session."""
        return await self._api_request(f"v1/sessions/{session_id}/")

    async def async_get_session_temps(
        self, 
        session_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get temperature readings for a session."""
        return await self._api_request(f"v1/sessions/{session_id}/temps/")