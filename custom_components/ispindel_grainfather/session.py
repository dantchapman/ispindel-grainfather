"""Brew session records and their persistent store.

A session deliberately stores only a name, a recipe link and a time window.
The gravity and temperature measurements already live in Home Assistant's
recorder, timestamped; copying them per session would create a second source of
truth that could drift. Everything else is derived by filtering on the window.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

STORAGE_VERSION = 1


@dataclass(slots=True)
class BrewSession:
    """One fermentation, from pitch to the day you call it done."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "Unnamed brew"
    recipe_url: str = ""
    pitched: str = ""
    ended: str | None = None
    og: float | None = None
    fg: float | None = None

    @property
    def pitched_dt(self) -> datetime | None:
        """Pitch time as a datetime."""
        return dt_util.parse_datetime(self.pitched) if self.pitched else None

    @property
    def ended_dt(self) -> datetime | None:
        """End time as a datetime, or None while still fermenting."""
        return dt_util.parse_datetime(self.ended) if self.ended else None

    @property
    def is_active(self) -> bool:
        """A session is active until it has been ended."""
        return self.ended is None

    @property
    def label(self) -> str:
        """Human-readable identifier, unique enough to pick from a list.

        The date is included because brewers reuse recipe names, and a select
        listing three identical "Northern Brown Ale" entries is useless.
        """
        when = self.pitched_dt
        stamp = dt_util.as_local(when).strftime("%d %b %Y") if when else "unknown"
        return f"{self.name} ({stamp})"

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the store."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BrewSession:
        """Rebuild from stored data, tolerating fields added in later versions."""
        known = {f for f in cls.__slots__}
        return cls(**{k: v for k, v in data.items() if k in known})


class SessionStore:
    """Persists brew sessions in Home Assistant's .storage."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialise the store."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"ispindel_grainfather_sessions_{entry_id}"
        )
        self.sessions: list[BrewSession] = []
        # Which session the UI is looking at. Not persisted as an id alone --
        # it is resolved on load, so a deleted session cannot leave a dangling
        # selection.
        self.selected_id: str | None = None

    async def async_load(self) -> None:
        """Load sessions from disk."""
        data = await self._store.async_load() or {}
        self.sessions = [
            BrewSession.from_dict(item) for item in data.get("sessions", [])
        ]
        self.sessions.sort(key=lambda s: s.pitched, reverse=True)
        selected = data.get("selected_id")
        self.selected_id = selected if self._find(selected) else None
        if self.selected_id is None:
            active = self.active
            self.selected_id = active.id if active else (
                self.sessions[0].id if self.sessions else None
            )

    async def async_save(self) -> None:
        """Write sessions to disk."""
        await self._store.async_save(
            {
                "sessions": [s.to_dict() for s in self.sessions],
                "selected_id": self.selected_id,
            }
        )

    # -- lookups -----------------------------------------------------------

    def _find(self, session_id: str | None) -> BrewSession | None:
        if not session_id:
            return None
        return next((s for s in self.sessions if s.id == session_id), None)

    @property
    def active(self) -> BrewSession | None:
        """The session currently fermenting, if any."""
        return next((s for s in self.sessions if s.is_active), None)

    @property
    def selected(self) -> BrewSession | None:
        """The session being viewed."""
        return self._find(self.selected_id) or self.active or (
            self.sessions[0] if self.sessions else None
        )

    def by_label(self, label: str) -> BrewSession | None:
        """Resolve a session from its select-list label."""
        return next((s for s in self.sessions if s.label == label), None)

    @property
    def labels(self) -> list[str]:
        """Select options, newest first."""
        return [s.label for s in self.sessions]

    # -- mutations ---------------------------------------------------------

    async def async_start(
        self,
        name: str,
        recipe_url: str = "",
        og: float | None = None,
        pitched: datetime | None = None,
    ) -> BrewSession:
        """Begin a new session, ending any that is still running.

        Ending the previous one automatically prevents two sessions claiming
        overlapping windows, which would make the chart ambiguous.
        """
        if (current := self.active) is not None:
            current.ended = dt_util.utcnow().isoformat()

        session = BrewSession(
            name=name or "Unnamed brew",
            recipe_url=recipe_url or "",
            pitched=(pitched or dt_util.utcnow()).isoformat(),
            og=og,
        )
        self.sessions.insert(0, session)
        self.sessions.sort(key=lambda s: s.pitched, reverse=True)
        self.selected_id = session.id
        await self.async_save()
        return session

    async def async_end(self, fg: float | None = None) -> BrewSession | None:
        """End the active session."""
        session = self.active
        if session is None:
            return None
        session.ended = dt_util.utcnow().isoformat()
        session.fg = fg
        await self.async_save()
        return session

    async def async_update_selected(self, **changes: Any) -> BrewSession | None:
        """Edit fields on the session currently being viewed.

        Edits target the viewed session rather than the active one so that a
        finished brew can be corrected after the fact -- which is the usual
        case for gravity, since the reliable reading comes from a hydrometer
        sample taken at bottling, long after the yeast has stopped.
        """
        session = self.selected
        if session is None:
            return None
        for key, value in changes.items():
            if hasattr(session, key):
                setattr(session, key, value)
        await self.async_save()
        return session

    async def async_update_active(self, **changes: Any) -> BrewSession | None:
        """Edit fields on the active session."""
        session = self.active
        if session is None:
            return None
        for key, value in changes.items():
            if hasattr(session, key):
                setattr(session, key, value)
        await self.async_save()
        return session

    async def async_select(self, session_id: str) -> None:
        """Change which session is being viewed."""
        if self._find(session_id):
            self.selected_id = session_id
            await self.async_save()

    async def async_delete(self, session_id: str) -> None:
        """Remove a session record. Measurements are untouched."""
        self.sessions = [s for s in self.sessions if s.id != session_id]
        if self.selected_id == session_id:
            self.selected_id = None
            await self.async_load_selection_fallback()
        await self.async_save()

    async def async_load_selection_fallback(self) -> None:
        """Point the selection at something sensible after a deletion."""
        active = self.active
        self.selected_id = active.id if active else (
            self.sessions[0].id if self.sessions else None
        )
