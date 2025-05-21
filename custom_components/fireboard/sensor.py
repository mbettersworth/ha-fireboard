"""Sensor platform for Fireboard integration."""
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    COORDINATOR,
    API,
    ATTR_CHANNEL,
    ATTR_DEVICE_ID,
    ATTR_LAST_UPDATED,
    ATTR_FIRMWARE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Fireboard sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    api = hass.data[DOMAIN][entry.entry_id][API]

    entities = []

    if coordinator.data:
        for device in coordinator.data:
            device_id = device.get("id")
            device_name = device.get("title", f"Fireboard {device_id}")
            model = device.get("hw_ver", "Fireboard 2")
            
            # Add temperature sensors for each channel
            for channel in device.get("channels", []):
                channel_id = channel.get("id")
                channel_name = channel.get("title", f"Channel {channel.get('channel')}")
                channel_number = channel.get("channel")
                
                entities.append(
                    FireboardTemperatureSensor(
                        coordinator,
                        api,
                        entry.entry_id,
                        device_id,
                        device_name,
                        model,
                        channel_id,
                        channel_name,
                        channel_number,
                    )
                )
    
    async_add_entities(entities)


class FireboardTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Fireboard temperature sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        api,
        config_entry_id: str,
        device_id: str,
        device_name: str,
        model: str,
        channel_id: str,
        channel_name: str,
        channel_number: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._config_entry_id = config_entry_id
        self._device_id = device_id
        self._device_name = device_name
        self._model = model
        self._channel_id = channel_id
        self._channel_name = channel_name
        self._channel_number = channel_number
        
        # Set sensor properties
        self._attr_name = f"{device_name} {channel_name}"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_channel_{channel_id}"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = TEMP_FAHRENHEIT
        
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Fireboard Labs",
            model=model,
        )
        
        self._attr_extra_state_attributes = {
            ATTR_DEVICE_ID: device_id,
            ATTR_CHANNEL: channel_number,
        }

    @property
    def native_value(self) -> Optional[float]:
        """Return the temperature value."""
        if not self.coordinator.data:
            return None
            
        # Find the device in coordinator data
        for device in self.coordinator.data:
            if str(device.get("id")) == str(self._device_id):
                # Check if device has temperature data
                if "temps" not in device:
                    return None
                    
                # Find the matching channel temperature
                for temp in device["temps"]:
                    if str(temp.get("channel")) == str(self._channel_number):
                        # Update last updated attribute
                        self._attr_extra_state_attributes[ATTR_LAST_UPDATED] = temp.get("time")
                        return float(temp.get("temp"))
                        
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Default method calls async_write_ha_state()
        super()._handle_coordinator_update()
        
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()