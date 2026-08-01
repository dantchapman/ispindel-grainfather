"""Shared entity base for the iSpindel → Grainfather integration."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_NEW_READING, SIGNAL_UPLOAD_RESULT
from .coordinator import IspindelRuntime


class IspindelEntity(Entity):
    """Base class wiring an entity to the runtime's dispatcher signals."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: IspindelRuntime, key: str) -> None:
        """Initialise the entity."""
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)},
            name=runtime.entry.title,
            manufacturer="iSpindel",
            model="DIY hydrometer",
            configuration_url=runtime.grainfather_url or None,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to the signals this entity cares about."""
        await super().async_added_to_hass()
        entry_id = self.runtime.entry.entry_id
        for signal in (SIGNAL_NEW_READING, SIGNAL_UPLOAD_RESULT):
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"{signal}_{entry_id}",
                    self._handle_update,
                )
            )

    @callback
    def _handle_update(self) -> None:
        """Redraw when the runtime has new data.

        The @callback decorator is load-bearing: without it the dispatcher
        treats this as a blocking function and runs it in an executor thread,
        where async_write_ha_state() is not allowed and the update is lost.
        """
        self.async_write_ha_state()
