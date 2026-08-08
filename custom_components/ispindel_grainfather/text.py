"""Editable fields for the active brew session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IspindelConfigEntry
from .coordinator import IspindelRuntime
from .session import BrewSession
from .session_entity import BrewSessionEntity


@dataclass(frozen=True, kw_only=True)
class BrewTextDescription(TextEntityDescription):
    """Describes an editable session field."""

    field: str
    value_fn: Callable[[BrewSession], str]


TEXTS: tuple[BrewTextDescription, ...] = (
    BrewTextDescription(
        key="name",
        translation_key="brew_name",
        icon="mdi:glass-mug-variant",
        native_max=100,
        field="name",
        value_fn=lambda s: s.name,
    ),
    BrewTextDescription(
        key="recipe_url",
        translation_key="recipe_url",
        icon="mdi:link-variant",
        native_max=255,
        field="recipe_url",
        value_fn=lambda s: s.recipe_url,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IspindelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the editable session fields."""
    runtime = entry.runtime_data
    async_add_entities(BrewText(runtime, d) for d in TEXTS)


class BrewText(BrewSessionEntity, TextEntity):
    """A field on the active brew session.

    Edits apply to the session in view, matching the sensors and the settable
    gravities, so what you are looking at is what you are editing.
    """

    entity_description: BrewTextDescription

    def __init__(
        self, runtime: IspindelRuntime, description: BrewTextDescription
    ) -> None:
        """Initialise the field."""
        super().__init__(runtime, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Editable whenever a session is in view."""
        return self.viewed is not None

    @property
    def native_value(self) -> str | None:
        """Current value on the viewed session."""
        session = self.viewed
        return self.entity_description.value_fn(session) if session else None

    async def async_set_value(self, value: str) -> None:
        """Write the value back to the viewed session."""
        await self.store.async_update_selected(
            **{self.entity_description.field: value}
        )
        self.runtime.async_notify_sessions()
