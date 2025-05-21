"""API client for Fireboard integration."""
import logging
import aiohttp
import asyncio
import async_timeout
import json
from typing import Optional, Dict, List, Any, Union, Tuple

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
        self.user_id = None
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # Track which API endpoints work
        self.working_endpoints = {}
        # Device cache to avoid repeated API calls
        self.device_cache = {}

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
                _LOGGER.debug(f"Authenticating with username: {self.username}")
                response = await session.post(
                    auth_url,
                    json={"username": self.username, "password": self.password},
                    headers=self.headers
                )
                
                if response.status == 200:
                    data = await response.json()
                    
                    if "key" in data:
                        self.token = data["key"]
                        self.headers["Authorization"] = f"Token {self.token}"
                        _LOGGER.info("Successfully authenticated with Fireboard API")
                        
                        # Get user profile immediately to capture user_id
                        profile = await self.get_user_profile()
                        if profile and "id" in profile:
                            self.user_id = profile["id"]
                            _LOGGER.debug(f"User ID captured: {self.user_id}")
                        
                        return True
                    else:
                        _LOGGER.error("Authentication succeeded but no token in response")
                        return False
                else:
                    status = response.status
                    text = await response.text()
                    _LOGGER.error(f"Authentication failed with status {status}: {text[:100]}")
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
        data: Optional[Dict] = None,
        raise_for_status: bool = True,
        version: Optional[str] = None
    ) -> Tuple[Optional[Dict], int]:
        """Make a request to the Fireboard API.
        
        Returns:
            Tuple containing (response_data, status_code)
        """
        # Ensure we're authenticated
        if not self.token and not await self.authenticate():
            _LOGGER.error("Authentication required for API requests")
            return None, 401
        
        # Construct URL with optional version
        if version:
            url = f"{self.api_url}/{version}/{endpoint.lstrip('/')}"
        else:
            url = f"{self.api_url}/{endpoint.lstrip('/')}"
            
        session = await self._get_session()
        
        try:
            with async_timeout.timeout(10):
                _LOGGER.debug(f"Making {method} request to {url}")
                
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
                    return None, 400

                status = response.status
                
                if status == 200:
                    try:
                        result = await response.json()
                        return result, status
                    except Exception as json_err:
                        text = await response.text()
                        _LOGGER.error(f"Failed to parse JSON response from {url}: {json_err}")
                        _LOGGER.debug(f"Raw response: {text[:200]}")
                        return None, status
                else:
                    if raise_for_status:
                        response.raise_for_status()
                    
                    text = await response.text()
                    _LOGGER.debug(f"API request to {url} returned {status}: {text[:100]}")
                    return None, status
                    
        except aiohttp.ClientResponseError as err:
            _LOGGER.debug(f"Response error from {url}: {err.status} - {err.message}")
            return None, err.status
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error requesting data from {url}: {err}")
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout calling {url}")
        except Exception as ex:
            _LOGGER.error(f"Unexpected error during API request to {url}: {ex}")
        
        return None, 500
        
    async def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """Get the current user's profile."""
        _LOGGER.debug("Getting user profile")
        profile, status = await self._api_request("rest-auth/user/")
        
        if profile:
            _LOGGER.debug(f"Successfully retrieved user profile: {json.dumps(profile)[:100]}...")
            if "id" in profile:
                self.user_id = profile["id"]
        else:
            _LOGGER.error(f"Failed to retrieve user profile, status code: {status}")
            
        return profile
    
    async def _discover_working_api_endpoints(self):
        """Discover which API endpoints are working for this installation."""
        if self.working_endpoints:
            return self.working_endpoints
            
        _LOGGER.debug("Discovering working API endpoints")
        
        # Get user profile first to capture user_id
        if not self.user_id:
            profile = await self.get_user_profile()
            if profile and "id" in profile:
                self.user_id = profile["id"]
        
        # List of API versions to try
        api_versions = ["v1", "v2", "v3", "v4", "drive", "cloud", "mobile", None]
        
        # List of endpoints to check for devices
        device_endpoints = [
            "devices",
            "device/list",
            "user/devices"
        ]
        
        # If we have a user_id, also try user-specific endpoints
        if self.user_id:
            device_endpoints.extend([
                f"users/{self.user_id}/devices",
                f"user/{self.user_id}/devices",
                f"accounts/{self.user_id}/devices"
            ])
        
        # Try each combination of version and endpoint
        for version in api_versions:
            for endpoint in device_endpoints:
                # Use appropriate endpoint construction
                if version:
                    # With version prefix
                    result, status = await self._api_request(
                        endpoint, 
                        raise_for_status=False,
                        version=version
                    )
                else:
                    # No version prefix
                    result, status = await self._api_request(
                        endpoint, 
                        raise_for_status=False
                    )
                
                # If we get a 200 OK, save this as a working endpoint
                if status == 200:
                    try:
                        # Check if we got valid data
                        if isinstance(result, list) or (isinstance(result, dict) and result):
                            key = f"devices_{version}" if version else "devices"
                            self.working_endpoints[key] = {"endpoint": endpoint, "version": version}
                            _LOGGER.info(f"Found working devices endpoint: {endpoint} (version: {version})")
                            
                            if isinstance(result, list):
                                _LOGGER.debug(f"Found {len(result)} devices")
                    except Exception as err:
                        _LOGGER.error(f"Error processing response for endpoint {endpoint}: {err}")
        
        _LOGGER.debug(f"Discovered working endpoints: {self.working_endpoints}")
        return self.working_endpoints
        
    async def get_devices(self) -> List[Dict[str, Any]]:
        """Get all Fireboard devices."""
        _LOGGER.debug("Getting all Fireboard devices")
        
        # First try to get devices from the user profile
        profile = await self.get_user_profile()
        
        if profile:
            # Check if devices are in the user profile
            if "userprofile" in profile and "devices" in profile["userprofile"]:
                devices = profile["userprofile"]["devices"]
                if devices:
                    _LOGGER.info(f"Found {len(devices)} devices in user profile")
                    return devices
            
            # Extract user ID if available
            if "id" in profile and not self.user_id:
                self.user_id = profile["id"]
                _LOGGER.debug(f"User ID from profile: {self.user_id}")
        
        # Discover working API endpoints
        await self._discover_working_api_endpoints()
        
        # Try the discovered endpoints for devices
        for key, endpoint_info in self.working_endpoints.items():
            if key.startswith("devices_"):
                endpoint = endpoint_info["endpoint"]
                version = endpoint_info["version"]
                
                _LOGGER.debug(f"Trying discovered endpoint: {endpoint} (version: {version})")
                result, status = await self._api_request(endpoint, version=version)
                
                if result is not None:
                    if isinstance(result, list):
                        _LOGGER.info(f"Found {len(result)} devices using endpoint: {endpoint} (version: {version})")
                        return result
                    elif isinstance(result, dict) and "devices" in result:
                        devices = result["devices"]
                        _LOGGER.info(f"Found {len(devices)} devices in 'devices' key using endpoint: {endpoint}")
                        return devices
                    elif isinstance(result, dict) and "results" in result:
                        devices = result["results"]
                        _LOGGER.info(f"Found {len(devices)} devices in 'results' key using endpoint: {endpoint}")
                        return devices
        
        # If all else fails, try a list of common API patterns
        endpoints_to_try = [
            {"endpoint": "devices", "version": None},
            {"endpoint": "devices", "version": "v1"},
            {"endpoint": "devices", "version": "v2"},
            {"endpoint": "devices", "version": "drive"},
            {"endpoint": "device/list", "version": None},
            {"endpoint": "user/devices", "version": None},
            {"endpoint": f"user/{self.user_id}/devices", "version": None} if self.user_id else None,
        ]
        
        endpoints_to_try = [e for e in endpoints_to_try if e is not None]
        
        for endpoint_info in endpoints_to_try:
            endpoint = endpoint_info["endpoint"]
            version = endpoint_info["version"]
            
            _LOGGER.debug(f"Trying fallback endpoint: {endpoint} (version: {version})")
            result, status = await self._api_request(endpoint, version=version)
            
            if result is not None:
                if isinstance(result, list):
                    _LOGGER.info(f"Found {len(result)} devices using fallback endpoint: {endpoint}")
                    return result
                elif isinstance(result, dict) and "devices" in result:
                    devices = result["devices"]
                    _LOGGER.info(f"Found {len(devices)} devices in 'devices' key using fallback endpoint: {endpoint}")
                    return devices
        
        # If we still can't find any devices, log detailed information
        _LOGGER.error("Could not find any devices through any API endpoints")
        _LOGGER.debug(f"User profile data: {json.dumps(profile)[:300]}..." if profile else "No user profile data")
        
        # Return an empty list to avoid None errors
        return []

    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific Fireboard device."""
        # Check cache first
        if device_id in self.device_cache:
            _LOGGER.debug(f"Using cached data for device {device_id}")
            return self.device_cache[device_id]
        
        _LOGGER.debug(f"Getting device details for {device_id}")
        
        # Try different possible endpoints based on discovered working endpoints
        endpoints_to_try = []
        
        # Add endpoints from discovered working endpoints
        for key, endpoint_info in self.working_endpoints.items():
            if key.startswith("devices_"):
                version = endpoint_info["version"]
                # Construct device detail endpoint from the devices list endpoint
                # This is a best guess based on RESTful API conventions
                endpoints_to_try.append({
                    "endpoint": f"devices/{device_id}", 
                    "version": version
                })
        
        # Add conventional endpoints as fallback
        endpoints_to_try.extend([
            {"endpoint": f"devices/{device_id}", "version": None},
            {"endpoint": f"devices/{device_id}", "version": "v1"},
            {"endpoint": f"devices/{device_id}", "version": "v2"},
            {"endpoint": f"devices/{device_id}", "version": "drive"},
            {"endpoint": f"device/{device_id}", "version": None},
        ])
        
        for endpoint_info in endpoints_to_try:
            endpoint = endpoint_info["endpoint"]
            version = endpoint_info["version"]
            
            _LOGGER.debug(f"Trying endpoint for device {device_id}: {endpoint} (version: {version})")
            result, status = await self._api_request(endpoint, version=version)
            
            if result is not None:
                _LOGGER.info(f"Found device {device_id} using endpoint: {endpoint} (version: {version})")
                # Save to cache
                self.device_cache[device_id] = result
                return result
        
        _LOGGER.error(f"Could not find device {device_id} through any API endpoints")
        return None

    async def get_temperatures(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get temperatures for a device."""
        _LOGGER.debug(f"Getting temperatures for device {device_id}")
        
        # Try different possible endpoints based on discovered working endpoints
        endpoints_to_try = []
        
        # Add endpoints from discovered working endpoints
        for key, endpoint_info in self.working_endpoints.items():
            if key.startswith("devices_"):
                version = endpoint_info["version"]
                # Construct temperature endpoint from the devices list endpoint
                endpoints_to_try.append({
                    "endpoint": f"devices/{device_id}/temps", 
                    "version": version
                })
                endpoints_to_try.append({
                    "endpoint": f"devices/{device_id}/temperatures", 
                    "version": version
                })
        
        # Add conventional endpoints as fallback
        endpoints_to_try.extend([
            {"endpoint": f"devices/{device_id}/temps", "version": None},
            {"endpoint": f"devices/{device_id}/temps", "version": "v1"},
            {"endpoint": f"devices/{device_id}/temperatures", "version": None},
            {"endpoint": f"device/{device_id}/temps", "version": None},
            {"endpoint": f"temps", "version": None, "params": {"device": device_id}},
        ])
        
        for endpoint_info in endpoints_to_try:
            endpoint = endpoint_info["endpoint"]
            version = endpoint_info["version"]
            params = endpoint_info.get("params")
            
            _LOGGER.debug(f"Trying endpoint for temperatures: {endpoint} (version: {version})")
            result, status = await self._api_request(endpoint, version=version, params=params)
            
            if result is not None:
                _LOGGER.info(f"Found temperatures for device {device_id} using endpoint: {endpoint} (version: {version})")
                return result
        
        _LOGGER.error(f"Could not find temperatures for device {device_id} through any API endpoints")
        return None

    async def get_alerts(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get alerts for a device."""
        _LOGGER.debug(f"Getting alerts for device {device_id}")
        
        # Try different possible endpoints based on discovered working endpoints
        endpoints_to_try = []
        
        # Add endpoints from discovered working endpoints
        for key, endpoint_info in self.working_endpoints.items():
            if key.startswith("devices_"):
                version = endpoint_info["version"]
                # Construct alert endpoint from the devices list endpoint
                endpoints_to_try.append({
                    "endpoint": f"devices/{device_id}/alerts", 
                    "version": version
                })
        
        # Add conventional endpoints as fallback
        endpoints_to_try.extend([
            {"endpoint": f"devices/{device_id}/alerts", "version": None},
            {"endpoint": f"devices/{device_id}/alerts", "version": "v1"},
            {"endpoint": f"device/{device_id}/alerts", "version": None},
            {"endpoint": f"alerts", "version": None, "params": {"device": device_id}},
        ])
        
        for endpoint_info in endpoints_to_try:
            endpoint = endpoint_info["endpoint"]
            version = endpoint_info["version"]
            params = endpoint_info.get("params")
            
            _LOGGER.debug(f"Trying endpoint for alerts: {endpoint} (version: {version})")
            result, status = await self._api_request(endpoint, version=version, params=params)
            
            if result is not None:
                _LOGGER.info(f"Found alerts for device {device_id} using endpoint: {endpoint} (version: {version})")
                return result
        
        _LOGGER.error(f"Could not find alerts for device {device_id} through any API endpoints")
        return None

    async def create_alert(
        self, 
        device_id: str, 
        channel_id: str, 
        min_temp: Optional[float] = None, 
        max_temp: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new alert."""
        _LOGGER.debug(f"Creating alert for device {device_id}, channel {channel_id}")
        
        data = {
            "device": device_id,
            "channel": channel_id
        }
        
        if min_temp is not None:
            data["min_temp"] = min_temp
        if max_temp is not None:
            data["max_temp"] = max_temp
        
        # Try different possible endpoints based on discovered working endpoints
        endpoints_to_try = []
        
        # Add endpoints from discovered working endpoints
        for key, endpoint_info in self.working_endpoints.items():
            if key.startswith("devices_"):
                version = endpoint_info["version"]
                # Construct alert endpoint from the devices list endpoint
                endpoints_to_try.append({
                    "endpoint": "alerts", 
                    "version": version
                })
                endpoints_to_try.append({
                    "endpoint": f"devices/{device_id}/alerts", 
                    "version": version
                })
        
        # Add conventional endpoints as fallback
        endpoints_to_try.extend([
            {"endpoint": "alerts", "version": None},
            {"endpoint": "alerts", "version": "v1"},
            {"endpoint": f"devices/{device_id}/alerts", "version": None},
        ])
        
        for endpoint_info in endpoints_to_try:
            endpoint = endpoint_info["endpoint"]
            version = endpoint_info["version"]
            
            _LOGGER.debug(f"Trying endpoint for creating alert: {endpoint} (version: {version})")
            result, status = await self._api_request(
                endpoint, 
                method="POST", 
                data=data,
                version=version
            )
            
            if result is not None:
                _LOGGER.info(f"Successfully created alert using endpoint: {endpoint} (version: {version})")
                return result
        
        _LOGGER.error(f"Could not create alert for device {device_id} through any API endpoints")
        return None

    async def delete_alert(self, alert_id):
        """Delete an alert."""
        _LOGGER.debug(f"Deleting alert {alert_id}")
        
        # Try different possible endpoints based on discovered working endpoints
        endpoints_to_try = []
        
        # Add endpoints from discovered working endpoints
        for key, endpoint_info in self.working_endpoints.items():
            if key.startswith("devices_"):
                version = endpoint_info["version"]
                # Construct alert endpoint from the devices list endpoint
                endpoints_to_try.append({
                    "endpoint": f"alerts/{alert_id}", 
                    "version": version
                })
        
        # Add conventional endpoints as fallback
        endpoints_to_try.extend([
            {"endpoint": f"alerts/{alert_id}", "version": None},
            {"endpoint": f"alerts/{alert_id}", "version": "v1"},
        ])
        
        for endpoint_info in endpoints_to_try:
            endpoint = endpoint_info["endpoint"]
            version = endpoint_info["version"]
            
            _LOGGER.debug(f"Trying endpoint for deleting alert: {endpoint} (version: {version})")
            result, status = await self._api_request(
                endpoint, 
                method="DELETE",
                version=version
            )
            
            if status == 204 or status == 200:
                _LOGGER.info(f"Successfully deleted alert {alert_id} using endpoint: {endpoint} (version: {version})")
                return True
        
        _LOGGER.error(f"Could not delete alert {alert_id} through any API endpoints")
        return False
