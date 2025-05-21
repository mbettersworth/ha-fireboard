"""Sensor platform for Fireboard integration."""
import logging
from datetime import datetime
import json

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN, COORDINATOR, API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Fireboard sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    api = hass.data[DOMAIN][entry.entry_id][API]

    entities = []

    # Always create the status sensor to show API connection status
    entities.append(FireboardStatusSensor(coordinator, api))

    # Only add additional entities if we have data
    if coordinator.data:
        _LOGGER.debug(f"Setting up entities with coordinator data: {json.dumps(coordinator.data)[:100]}...")
        
        # Add user profile sensor
        if "profile" in coordinator.data:
            profile = coordinator.data["profile"]
            user_id = profile.get("id")
            username = profile.get("username")
            
            if user_id and username:
                _LOGGER.info(f"Creating profile sensor for user {username} (ID: {user_id})")
                entities.append(FireboardProfileSensor(coordinator, api, user_id, username))
                
                # Create API Endpoints sensor to help with troubleshooting
                if "working_endpoints" in coordinator.data:
                    entities.append(
                        FireboardApiEndpointsSensor(
                            coordinator, 
                            api, 
                            user_id, 
                            username, 
                            coordinator.data["working_endpoints"]
                        )
                    )
        
        # Add device sensors
        devices = coordinator.data.get("devices", [])
        if devices:
            _LOGGER.info(f"Found {len(devices)} devices, creating sensors")
            for device in devices:
                device_id = device.get("id")
                device_name = device.get("title", f"Fireboard {device_id}")
                
                if not device_id:
                    _LOGGER.warning(f"Skipping device with no ID: {device}")
                    continue
                    
                _LOGGER.debug(f"Processing device: {device_id} - {device_name}")
                
                # Add device info sensor
                entities.append(FireboardDeviceSensor(coordinator, api, device_id, device_name))
                
                # Add sensors for each channel - if any are present
                channels = device.get("channels", [])
                if not channels:
                    _LOGGER.warning(f"No channels found for device {device_id} ({device_name})")
                
                for channel in channels:
                    channel_id = channel.get("id")
                    # Try multiple ways to get channel name/number
                    channel_name = channel.get("title") or channel.get("name") or f"Channel {channel.get('channel')}"
                    channel_number = channel.get("channel")
                    
                    if not channel_id:
                        _LOGGER.warning(f"Skipping channel with no ID: {channel}")
                        continue
                        
                    _LOGGER.debug(f"Adding temperature sensor for channel: {channel_id} - {channel_name}")
                    
                    entities.append(
                        FireboardTemperatureSensor(
                            coordinator, 
                            api, 
                            device_id, 
                            device_name,
                            channel_id,
                            channel_name,
                            channel_number
                        )
                    )
        else:
            # If no devices were found, add a diagnostic sensor to show API status
            profile = coordinator.data.get("profile", {})
            user_id = profile.get("id")
            username = profile.get("username", "Unknown")
            
            if user_id:
                _LOGGER.warning(f"No devices found for user {username}, creating troubleshooting sensor")
                entities.append(
                    FireboardTroubleshootingSensor(
                        coordinator, 
                        api, 
                        user_id, 
                        username,
                        entry.data.get("username", "Unknown")
                    )
                )

    _LOGGER.info(f"Adding {len(entities)} Fireboard entities")
    async_add_entities(entities)


class FireboardStatusSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Fireboard API status sensor."""

    def __init__(self, coordinator, api):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._state = "connecting"
        self._attr_unique_id = f"{DOMAIN}_api_status"
        self._attr_name = "Fireboard API Status"
        self._attributes = {
            "last_updated": datetime.now().isoformat(),
            "authenticated": False,
            "api_endpoints_discovered": 0,
            "devices_found": 0,
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.coordinator.last_update_success:
            self._state = "disconnected"
        elif self.coordinator.data:
            if self.coordinator.data.get("devices"):
                self._state = "connected"
            elif self.coordinator.data.get("profile"):
                self._state = "authenticated"
            else:
                self._state = "error"
        else:
            self._state = "connecting"
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # Update attributes from coordinator data
        if self.coordinator.data:
            # Update authentication status
            self._attributes["authenticated"] = bool(self.coordinator.data.get("profile"))
            
            # Update device count
            devices = self.coordinator.data.get("devices", [])
            self._attributes["devices_found"] = len(devices)
            
            # Update API endpoints info
            endpoints = self.coordinator.data.get("working_endpoints", {})
            self._attributes["api_endpoints_discovered"] = len(endpoints)
            
            # Add last error if present
            if "error" in self.coordinator.data:
                self._attributes["last_error"] = self.coordinator.data["error"]
                
            # Update last check timestamp
            self._attributes["last_updated"] = datetime.now().isoformat()
            
        return self._attributes

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()


class FireboardProfileSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Fireboard user profile sensor."""

    def __init__(self, coordinator, api, user_id, username):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._user_id = user_id
        self._username = username
        self._state = "connected"
        self._attr_unique_id = f"{DOMAIN}_user_{user_id}"
        self._attr_name = f"Fireboard User {username}"
        self._attributes = {
            "user_id": user_id,
            "username": username,
            "last_updated": datetime.now().isoformat(),
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # Update attributes from coordinator data
        if self.coordinator.data and "profile" in self.coordinator.data:
            profile = self.coordinator.data["profile"]
            
            # Add user profile information
            if "userprofile" in profile:
                user_profile = profile["userprofile"]
                for key, value in user_profile.items():
                    # Don't include complex nested objects
                    if isinstance(value, (str, int, float, bool)):
                        self._attributes[key] = value
            
            # Add basic user information
            for key in ["email", "first_name", "last_name"]:
                if key in profile:
                    self._attributes[key] = profile[key]
                    
            # Update last updated timestamp
            self._attributes["last_updated"] = datetime.now().isoformat()
            
        return self._attributes

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()


class FireboardApiEndpointsSensor(CoordinatorEntity, SensorEntity):
    """Representation of Fireboard API endpoints for troubleshooting."""

    def __init__(self, coordinator, api, user_id, username, endpoints):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._user_id = user_id
        self._username = username
        self._endpoints = endpoints
        self._state = str(len(endpoints))
        self._attr_unique_id = f"{DOMAIN}_api_endpoints_{user_id}"
        self._attr_name = f"Fireboard API Endpoints"
        self._attributes = {
            "user_id": user_id,
            "username": username,
            "endpoint_count": len(endpoints),
            "endpoints": endpoints,
            "last_updated": datetime.now().isoformat(),
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "working_endpoints" in self.coordinator.data:
            self._endpoints = self.coordinator.data["working_endpoints"]
            self._state = str(len(self._endpoints))
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # Update attributes from coordinator data
        if self.coordinator.data and "working_endpoints" in self.coordinator.data:
            self._endpoints = self.coordinator.data["working_endpoints"]
            self._attributes["endpoint_count"] = len(self._endpoints)
            self._attributes["endpoints"] = self._endpoints
            self._attributes["last_updated"] = datetime.now().isoformat()
            
        return self._attributes

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()


class FireboardTroubleshootingSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Fireboard troubleshooting sensor when no devices found."""

    def __init__(self, coordinator, api, user_id, username, email):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._user_id = user_id
        self._username = username
        self._email = email
        self._state = "no_devices"
        self._attr_unique_id = f"{DOMAIN}_troubleshoot_{user_id}"
        self._attr_name = f"Fireboard Troubleshooting"
        self._attributes = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "api_status": "authenticated",
            "devices_found": 0,
            "possible_issues": [
                "API endpoint structure changed",
                "No devices registered with this account",
                "Devices not available through API"
            ],
            "troubleshooting_steps": [
                "Verify device is registered in Fireboard app",
                "Ensure correct email is used for authentication",
                "Check Fireboard cloud service status"
            ],
            "last_updated": datetime.now().isoformat(),
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # Update authentication status from coordinator data
        if self.coordinator.data:
            if "profile" in self.coordinator.data:
                self._attributes["api_status"] = "authenticated"
            else:
                self._attributes["api_status"] = "authentication_failed"
                
            devices = self.coordinator.data.get("devices", [])
            self._attributes["devices_found"] = len(devices)
            
            # Add API endpoint info if available
            if "working_endpoints" in self.coordinator.data:
                self._attributes["working_endpoints"] = self.coordinator.data["working_endpoints"]
                
            # Add any errors
            if "error" in self.coordinator.data:
                self._attributes["error"] = self.coordinator.data["error"]
                
            # Update last check timestamp
            self._attributes["last_updated"] = datetime.now().isoformat()
            
        return self._attributes

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()


class FireboardDeviceSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Fireboard device sensor."""

    def __init__(self, coordinator, api, device_id, device_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_id
        self._device_name = device_name
        self._state = "connected"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_info"
        self._attr_name = f"{device_name} Info"
        self._attributes = {
            "device_id": device_id,
            "device_name": device_name,
            "last_updated": datetime.now().isoformat(),
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def state(self):
        """Return the state of the sensor."""
        # Check if device is in the latest data
        if self.coordinator.data and "devices" in self.coordinator.data:
            devices = self.coordinator.data["devices"]
            for device in devices:
                if str(device.get("id")) == str(self._device_id):
                    self._state = "connected"
                    break
            else:
                self._state = "disconnected"
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # Try to update device attributes from coordinator data
        if self.coordinator.data and "devices" in self.coordinator.data:
            devices = self.coordinator.data["devices"]
            for device in devices:
                if str(device.get("id")) == str(self._device_id):
                    # Add device properties as attributes
                    for key, value in device.items():
                        if isinstance(value, (str, int, float, bool)):
                            self._attributes[key] = value
                        elif key == "channels":
                            self._attributes["channel_count"] = len(value)
                    
                    # Update last updated timestamp
                    self._attributes["last_updated"] = datetime.now().isoformat()
                    break
                    
        return self._attributes

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()


class FireboardTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Fireboard temperature sensor."""

    def __init__(self, coordinator, api, device_id, device_name, channel_id, channel_name, channel_number):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_id
        self._device_name = device_name
        self._channel_id = channel_id
        self._channel_name = channel_name
        self._channel_number = channel_number
        self._state = None
        self._unit = UnitOfTemperature.FAHRENHEIT
        self._attr_unique_id = f"{DOMAIN}_{device_id}_channel_{channel_id}"
        self._attr_name = f"Fireboard {device_name} {channel_name}"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attributes = {
            "device_id": device_id,
            "device_name": device_name,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "channel_number": channel_number,
            "last_updated": datetime.now().isoformat(),
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def state(self):
        """Return the state of the sensor."""
        # Find the current device and channel in coordinator data
        if self.coordinator.data and "devices" in self.coordinator.data:
            devices = self.coordinator.data["devices"]
            for device in devices:
                if str(device.get("id")) == str(self._device_id):
                    for channel in device.get("channels", []):
                        if str(channel.get("id")) == str(self._channel_id):
                            # Try different possible temperature field names
                            temp_field_names = ["temp", "temperature", "current_temp", "value"]
                            for field in temp_field_names:
                                if field in channel and channel[field] is not None:
                                    self._state = channel[field]
                                    break
                            
                            # Update channel attributes
                            for key, value in channel.items():
                                if isinstance(value, (str, int, float, bool)):
                                    self._attributes[key] = value
                            # Update last_updated attribute
                            self._attributes["last_updated"] = datetime.now().isoformat()
                            break
        
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        # Check if unit is provided in the data, otherwise use default
        if self.coordinator.data and "devices" in self.coordinator.data:
            devices = self.coordinator.data["devices"]
            for device in devices:
                if str(device.get("id")) == str(self._device_id):
                    for channel in device.get("channels", []):
                        if str(channel.get("id")) == str(self._channel_id):
                            unit = channel.get("unit", "").upper()
                            if "F" in unit:
                                self._unit = UnitOfTemperature.FAHRENHEIT
                            elif "C" in unit:
                                self._unit = UnitOfTemperature.CELSIUS
        return self._unit

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()
