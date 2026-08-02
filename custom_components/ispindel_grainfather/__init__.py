"""The iSpindel → Grainfather integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_FG,
    ATTR_OG,
    ATTR_PITCHED,
    ATTR_RECIPE_URL,
    ATTR_SESSION_ID,
    ATTR_SESSION_NAME,
    DOMAIN,
    SERVICE_DELETE_SESSION,
    SERVICE_END_SESSION,
    SERVICE_START_SESSION,
    SIGNAL_SESSIONS,
)
from .coordinator import IspindelRuntime
from .session import SessionStore

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

type IspindelConfigEntry = ConfigEntry[IspindelRuntime]

START_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SESSION_NAME): cv.string,
        vol.Optional(ATTR_RECIPE_URL): cv.string,
        vol.Optional(ATTR_OG): vol.Coerce(float),
        # Optional so a session can be back-filled with its real pitch time
        # rather than the moment the service happened to be called.
        vol.Optional(ATTR_PITCHED): cv.datetime,
    }
)
END_SCHEMA = vol.Schema({vol.Optional(ATTR_FG): vol.Coerce(float)})
DELETE_SCHEMA = vol.Schema({vol.Required(ATTR_SESSION_ID): cv.string})


async def async_setup_entry(hass: HomeAssistant, entry: IspindelConfigEntry) -> bool:
    """Set up one configured iSpindel."""
    runtime = IspindelRuntime(hass, entry)
    runtime.sessions = SessionStore(hass, entry.entry_id)
    await runtime.sessions.async_load()
    await runtime.async_start()
    entry.runtime_data = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    _async_register_services(hass)
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


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the brew-session services once."""
    if hass.services.has_service(DOMAIN, SERVICE_START_SESSION):
        return

    def _runtimes() -> list[IspindelRuntime]:
        return [
            e.runtime_data
            for e in hass.config_entries.async_entries(DOMAIN)
            if hasattr(e, "runtime_data") and e.runtime_data is not None
        ]

    async def _start(call: ServiceCall) -> None:
        for runtime in _runtimes():
            pitched = call.data.get(ATTR_PITCHED)
            await runtime.sessions.async_start(
                name=call.data[ATTR_SESSION_NAME],
                recipe_url=call.data.get(ATTR_RECIPE_URL, ""),
                og=call.data.get(ATTR_OG, runtime.current_gravity),
                pitched=dt_util.as_utc(pitched) if pitched else None,
            )
            runtime.async_notify_sessions()

    async def _end(call: ServiceCall) -> None:
        for runtime in _runtimes():
            await runtime.sessions.async_end(
                fg=call.data.get(ATTR_FG, runtime.current_gravity)
            )
            runtime.async_notify_sessions()

    async def _delete(call: ServiceCall) -> None:
        for runtime in _runtimes():
            await runtime.sessions.async_delete(call.data[ATTR_SESSION_ID])
            runtime.async_notify_sessions()

    hass.services.async_register(DOMAIN, SERVICE_START_SESSION, _start, START_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_END_SESSION, _end, END_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_SESSION, _delete, DELETE_SCHEMA)


def async_notify_sessions(hass: HomeAssistant, entry_id: str) -> None:
    """Tell session entities to redraw."""
    async_dispatcher_send(hass, f"{SIGNAL_SESSIONS}_{entry_id}")
