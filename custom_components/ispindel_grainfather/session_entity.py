"""Shared base for brew-session entities.

These live on their own device rather than under the iSpindel: a brew session
is a record about the beer, not a property of the hydrometer, and separating
them keeps the device pages readable.
"""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_NEW_READING, SIGNAL_SESSIONS
from .coordinator import IspindelRuntime
from .session import BrewSession


class BrewSessionEntity(Entity):
    """Base class for entities describing a brew session."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: IspindelRuntime, key: str) -> None:
        """Initialise the entity."""
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_session_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{runtime.entry.entry_id}_session")},
            name="Brew Session",
            manufacturer="iSpindel → Grainfather",
            model="Fermentation log",
            entry_type=None,
        )

    @property
    def store(self):
        """The session store."""
        return self.runtime.sessions

    @property
    def viewed(self) -> BrewSession | None:
        """The session currently being looked at."""
        return self.store.selected if self.store else None

    @property
    def active(self) -> BrewSession | None:
        """The session currently fermenting, if any."""
        return self.store.active if self.store else None

    async def async_added_to_hass(self) -> None:
        """Redraw on session changes and on new readings.

        New readings matter because the derived figures -- attenuation, ABV --
        track live gravity while a session is still running.
        """
        await super().async_added_to_hass()
        entry_id = self.runtime.entry.entry_id
        for signal in (SIGNAL_SESSIONS, SIGNAL_NEW_READING):
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass, f"{signal}_{entry_id}", self._handle_update
                )
            )

    @callback
    def _handle_update(self) -> None:
        """Redraw. The @callback decorator is load-bearing -- see entity.py."""
        self.async_write_ha_state()
