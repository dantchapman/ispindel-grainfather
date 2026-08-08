"""Manually settable gravities for a brew session.

The iSpindel's snapshot is a convenience, not the truth. A floating hydrometer
accumulates yeast and can drift over a fermentation, so the figure worth
keeping is usually a hydrometer sample taken at bottling. These entities let
that number be recorded against the session, and every derived figure --
attenuation, ABV -- follows from them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IspindelConfigEntry
from .coordinator import IspindelRuntime
from .session import BrewSession
from .session_entity import BrewSessionEntity


@dataclass(frozen=True, kw_only=True)
class BrewNumberDescription(NumberEntityDescription):
    """Describes a settable gravity on a brew session."""

    field: str
    value_fn: Callable[[BrewSession], float | None]


NUMBERS: tuple[BrewNumberDescription, ...] = (
    BrewNumberDescription(
        key="og_set",
        translation_key="og_set",
        icon="mdi:water-percent",
        native_min_value=0.980,
        native_max_value=1.200,
        native_step=0.0001,
        native_unit_of_measurement="SG",
        mode=NumberMode.BOX,
        field="og",
        value_fn=lambda s: s.og,
    ),
    BrewNumberDescription(
        key="fg_set",
        translation_key="fg_set",
        icon="mdi:water-percent",
        native_min_value=0.980,
        native_max_value=1.200,
        native_step=0.0001,
        native_unit_of_measurement="SG",
        mode=NumberMode.BOX,
        field="fg",
        value_fn=lambda s: s.fg,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IspindelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the settable gravities."""
    runtime = entry.runtime_data
    async_add_entities(BrewNumber(runtime, d) for d in NUMBERS)


class BrewNumber(BrewSessionEntity, NumberEntity):
    """A gravity you can type in, overriding whatever the iSpindel captured."""

    entity_description: BrewNumberDescription

    def __init__(
        self, runtime: IspindelRuntime, description: BrewNumberDescription
    ) -> None:
        """Initialise the entity."""
        super().__init__(runtime, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Editable whenever a session is in view."""
        return self.viewed is not None

    @property
    def native_value(self) -> float | None:
        """Current value on the viewed session."""
        session = self.viewed
        return self.entity_description.value_fn(session) if session else None

    async def async_set_native_value(self, value: float) -> None:
        """Record the value against the viewed session."""
        await self.store.async_update_selected(
            **{self.entity_description.field: round(value, 4)}
        )
        self.runtime.async_notify_sessions()
