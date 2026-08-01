"""Manual upload button for the iSpindel → Grainfather integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IspindelConfigEntry
from .coordinator import IspindelRuntime
from .entity import IspindelEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IspindelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the manual upload button."""
    async_add_entities([GrainfatherUploadNow(entry.runtime_data)])


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
