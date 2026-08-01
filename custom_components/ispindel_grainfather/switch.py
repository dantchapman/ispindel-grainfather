"""Forwarding switch for the iSpindel → Grainfather integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import IspindelConfigEntry
from .coordinator import IspindelRuntime
from .entity import IspindelEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IspindelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the forwarding switch."""
    async_add_entities([GrainfatherForwarding(entry.runtime_data)])


class GrainfatherForwarding(IspindelEntity, SwitchEntity, RestoreEntity):
    """Master switch for uploads to Grainfather.

    Home Assistant keeps recording locally whatever this is set to; only the
    outbound leg is gated. Defaults to off so that bench testing an
    uncalibrated device cannot pollute a live brew session.
    """

    _attr_translation_key = "forwarding"
    _attr_icon = "mdi:cloud-upload-outline"

    def __init__(self, runtime: IspindelRuntime) -> None:
        """Initialise the switch."""
        super().__init__(runtime, "forwarding")

    async def async_added_to_hass(self) -> None:
        """Restore the previous choice across restarts."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self.runtime.forwarding_enabled = last_state.state == "on"

    @property
    def is_on(self) -> bool:
        """Return whether uploads are armed."""
        return self.runtime.forwarding_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Arm uploads."""
        self.runtime.forwarding_enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disarm uploads."""
        self.runtime.forwarding_enabled = False
        self.async_write_ha_state()
