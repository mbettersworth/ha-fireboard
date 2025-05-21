"""API client for Fireboard integration."""
import logging
import aiohttp
import asyncio
import async_timeout
from typing import Optional, Dict, List, Any

_LOGGER = logging.getLogger(__name__)

class FireboardApiClient:
    """API client for Fireboard integration."""

    def __init__(
        self, 
        hass, 
        username: Optional[str] = None,
        password: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None
    ):
        """Initialize the API client.
        
        Args:
            hass: Home Assistant instance
            username: Fireboard username (email)
            password: Fireboard password
            session: Optional existing aiohttp ClientSession
        """
        self.hass = hass
        self.username = username
        self.password = password
        self.api_url = "https://fireboard.io/api"
        self.token = None
        self.session = session
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def _get_session(self):
        """Get an aiohttp ClientSession."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def authenticate(self) -> bool:
        """Authenticate with the Fireboard API."""
        if not self.username or not self.password:
            _LOGGER.error("Username and password are required for authentication")
            return False

        session = await self._get_session()
        auth_url = f"{self.api_url}/rest-auth/login/"
        
        try:
            with async_timeout.timeout(10):
                response = await session.post(
                    auth_url,
                    json={"username": self.username, "password": self.password},
                    headers=self.headers
                )
                response.raise_for_status()
                data = await response.json()
                
                if "key" in data:
                    self.token = data["key"]
                    self.headers["Authorization"] = f"Token {self.token}"
                    _LOGGER.info("Successfully authenticated with Fireboard API")
                    return True
                else:
                    _LOGGER.error("Authentication succeeded but no token in response")
                    return False
                    
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error authenticating with Fireboard API: {err}")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout during authentication with Fireboard API")
        except Exception as ex:
            _LOGGER.error(f"Unexpected error during authentication: {ex}")
        
        return False

    async def _api_request(
        self, 
        endpoint: str, 
        method: str = "GET", 
        params: Optional[Dict] = None, 
        data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make a request to the Fireboard API."""
        # Ensure we're authenticated
        if not self.token and not await self.authenticate():
            _LOGGER.error("Authentication required for API requests")
            return None
            
        session = await self._get_session()
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        try:
            with async_timeout.timeout(10):
                if method == "GET":
                    response = await session.get(url, headers=self.headers, params=params)
                elif method == "POST":
                    response = await session.post(url, headers=self.headers, json=data)
                elif method == "PUT":
                    response = await session.put(url, headers=self.headers, json=data)
                elif method == "DELETE":
                    response = await session.delete(url, headers=self.headers)
                else:
                    _LOGGER.error(f"Unsupported method: {method}")
                    return None

                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error requesting data from {url}: {err}")
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout calling {url}")
        except Exception as ex:
            _LOGGER.error(f"Unexpected error during API request: {ex}")
        
        return None
        
    async def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """Get the current user's profile."""
        return await self._api_request("rest-auth/user/")
        
    async def get_devices(self) -> Optional[List[Dict[str, Any]]]:
        """Get all Fireboard devices."""
        # First try to get devices from the user profile
        profile = await self.get_user_profile()
        if profile and "userprofile" in profile:
            # Check if devices are in the user profile
            devices = profile.get("userprofile", {}).get("devices", [])
            if devices:
                return devices
        
        # Try different possible endpoints
        endpoints = [
            "devices",
            "v1/devices",
            "drive/devices"
        ]
        
        for endpoint in endpoints:
            result = await self._api_request(endpoint)
            if result is not None:
                _LOGGER.info(f"Found devices using endpoint: {endpoint}")
                return result
        
        return []

    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific Fireboard device."""
        # Try different possible endpoints
        endpoints = [
            f"v1/devices/{device_id}",
            f"devices/{device_id}",
            f"drive/devices/{device_id}"
        ]
        
        for endpoint in endpoints:
            result = await self._api_request(endpoint)
            if result is not None:
                return result
        
        return None

    async def get_temperatures(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get temperatures for a device."""
        # Try different possible endpoints
        endpoints = [
            f"v1/devices/{device_id}/temps",
            f"devices/{device_id}/temps",
            f"drive/devices/{device_id}/temps"
        ]
        
        for endpoint in endpoints:
            result = await self._api_request(endpoint)
            if result is not None:
                return result
        
        return None

    async def get_alerts(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get alerts for a device."""
        # Try different possible endpoints
        endpoints = [
            f"v1/devices/{device_id}/alerts",
            f"devices/{device_id}/alerts",
            f"drive/devices/{device_id}/alerts"
        ]
        
        for endpoint in endpoints:
            result = await self._api_request(endpoint)
            if result is not None:
                return result
        
        return None

    async def create_alert(
        self, 
        device_id: str, 
        channel_id: str, 
        min_temp: Optional[float] = None, 
        max_temp: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new alert."""
        data = {
            "device": device_id,
            "channel": channel_id
        }
        
        if min_temp is not None:
            data["min"] = min_temp
        if max_temp is not None:
            data["max"] = max_temp
        
        # Try different possible endpoints
        endpoints = [
            "v1/alerts",
            "alerts",
            "drive/alerts"
        ]
        
        for endpoint in endpoints:
            result = await self._api_request(endpoint, method="POST", data=data)
            if result is not None:
                return result
        
        return None

    async def delete_alert(self, alert_id):
        """Delete an alert."""
        return await self._api_request(f"alerts/{alert_id}", method="DELETE")
