"""Connectivity entity for the iSpindel → Grainfather integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import IspindelConfigEntry
from .coordinator import IspindelRuntime
from .entity import IspindelEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IspindelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the connectivity sensor."""
    async_add_entities([IspindelOnline(entry.runtime_data)])


class IspindelOnline(IspindelEntity, BinarySensorEntity):
    """Whether the iSpindel is still reporting."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "online"

    def __init__(self, runtime: IspindelRuntime) -> None:
        """Initialise the entity."""
        super().__init__(runtime, "online")

    @property
    def is_on(self) -> bool:
        """Return True while the device is reporting on schedule."""
        return self.runtime.is_online

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose how long it has been quiet, for troubleshooting."""
        reading = self.runtime.last_reading
        if reading is None:
            return None
        age = (dt_util.utcnow() - reading.received).total_seconds()
        return {
            "seconds_since_report": round(age),
            "reported_interval": reading.interval,
        }
