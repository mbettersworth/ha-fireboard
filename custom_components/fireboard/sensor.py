"""Sensor platform for Fireboard integration."""
import logging
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    TEMP_FAHRENHEIT,
    TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE,
)
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

    # Only add entities if we have data
    if coordinator.data:
        for device in coordinator.data:
            device_id = device.get("id")
            device_name = device.get("name", f"Fireboard {device_id}")
            
            # Add device info sensor
            entities.append(FireboardDeviceSensor(coordinator, api, device_id, device_name))
            
            # Add sensors for each channel
            for channel in device.get("channels", []):
                channel_id = channel.get("id")
                channel_name = channel.get("name", f"Channel {channel.get('channel')}")
                channel_number = channel.get("channel")
                
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

    async_add_entities(entities)


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
        self._unit = TEMP_FAHRENHEIT
        self._attr_unique_id = f"{DOMAIN}_{device_id}_channel_{channel_id}"
        self._attr_name = f"{device_name} {channel_name}"
        self._attr_device_class = DEVICE_CLASS_TEMPERATURE
        self._attributes = {
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
        if self.coordinator.data:
            for device in self.coordinator.data:
                if str(device.get("id")) == str(self._device_id):
                    for channel in device.get("channels", []):
                        if str(channel.get("id")) == str(self._channel_id):
                            self._state = channel.get("temp")
                            # Update last_updated attribute
                            self._attributes["last_updated"] = datetime.now().isoformat()
                            break
        
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()
