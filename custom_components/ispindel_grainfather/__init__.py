"""The iSpindel → Grainfather integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import IspindelRuntime

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

type IspindelConfigEntry = ConfigEntry[IspindelRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: IspindelConfigEntry) -> bool:
    """Set up one configured iSpindel."""
    runtime = IspindelRuntime(hass, entry)
    await runtime.async_start()
    entry.runtime_data = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IspindelConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.async_stop()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: IspindelConfigEntry) -> None:
    """Reload when options change, so timer and units are rebuilt."""
    await hass.config_entries.async_reload(entry.entry_id)
