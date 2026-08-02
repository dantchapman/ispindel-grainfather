"""Buttons for the iSpindel → Grainfather integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IspindelConfigEntry
from .coordinator import IspindelRuntime
from .entity import IspindelEntity
from .session_entity import BrewSessionEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IspindelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the buttons."""
    runtime = entry.runtime_data
    async_add_entities(
        [
            GrainfatherUploadNow(runtime),
            BrewPitchButton(runtime),
            BrewEndButton(runtime),
        ]
    )


class GrainfatherUploadNow(IspindelEntity, ButtonEntity):
    """Send the most recent reading to Grainfather immediately.

    Bypasses the forwarding switch and the timer, but not the need for a
    reading -- it is for confirming the endpoint works without waiting out an
    interval.
    """

    _attr_translation_key = "upload_now"
    _attr_icon = "mdi:cloud-upload"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime: IspindelRuntime) -> None:
        """Initialise the button."""
        super().__init__(runtime, "upload_now")

    @property
    def available(self) -> bool:
        """Only offer the button when there is something to send."""
        return self.runtime.last_reading is not None

    async def async_press(self) -> None:
        """Upload now."""
        await self.runtime.async_upload()


class BrewPitchButton(BrewSessionEntity, ButtonEntity):
    """Start a new brew session at this moment."""

    _attr_translation_key = "pitch"
    _attr_icon = "mdi:beaker-plus-outline"

    def __init__(self, runtime: IspindelRuntime) -> None:
        """Initialise the button."""
        super().__init__(runtime, "pitch")

    @property
    def available(self) -> bool:
        """Disabled while a brew is already running.

        Starting a second session would otherwise silently end the first, and
        two overlapping windows make the chart ambiguous. End the current brew
        first, or use the start_session service if that is really what you want.
        """
        return self.active is None

    async def async_press(self) -> None:
        """Begin a session, snapshotting OG from the current reading."""
        previous = self.store.sessions[0] if self.store.sessions else None
        await self.store.async_start(
            name=previous.name if previous else "Unnamed brew",
            recipe_url="",
            og=self.runtime.current_gravity,
        )
        self.runtime.async_notify_sessions()
        # Pitching is the point at which the brew becomes real, so start
        # relaying to Grainfather rather than relying on remembering.
        self.runtime.forwarding_enabled = True


class BrewEndButton(BrewSessionEntity, ButtonEntity):
    """Close off the running brew session."""

    _attr_translation_key = "end_fermentation"
    _attr_icon = "mdi:beaker-check-outline"

    def __init__(self, runtime: IspindelRuntime) -> None:
        """Initialise the button."""
        super().__init__(runtime, "end")

    @property
    def available(self) -> bool:
        """Only meaningful while a brew is running."""
        return self.active is not None

    async def async_press(self) -> None:
        """End the session, snapshotting FG.

        Deliberately leaves Grainfather forwarding alone -- cold crashing and
        conditioning are still worth logging.
        """
        await self.store.async_end(fg=self.runtime.current_gravity)
        self.runtime.async_notify_sessions()
