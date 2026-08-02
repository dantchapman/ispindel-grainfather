"""Session picker for the iSpindel → Grainfather integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IspindelConfigEntry
from .coordinator import IspindelRuntime
from .session_entity import BrewSessionEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IspindelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the session selector."""
    async_add_entities([BrewSessionSelect(entry.runtime_data)])


class BrewSessionSelect(BrewSessionEntity, SelectEntity):
    """Chooses which brew session the sensors and chart describe."""

    _attr_translation_key = "session"
    _attr_icon = "mdi:format-list-bulleted"

    def __init__(self, runtime: IspindelRuntime) -> None:
        """Initialise the selector."""
        super().__init__(runtime, "select")

    @property
    def options(self) -> list[str]:
        """Every recorded session, newest first."""
        return self.store.labels if self.store else []

    @property
    def current_option(self) -> str | None:
        """The session being viewed."""
        session = self.viewed
        return session.label if session else None

    @property
    def available(self) -> bool:
        """Nothing to select until a brew has been pitched."""
        return bool(self.options)

    async def async_select_option(self, option: str) -> None:
        """Change the viewed session."""
        if (session := self.store.by_label(option)) is not None:
            await self.store.async_select(session.id)
            self.runtime.async_notify_sessions()
