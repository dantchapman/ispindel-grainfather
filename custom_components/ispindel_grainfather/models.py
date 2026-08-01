"""Data model and unit conversion for iSpindel readings."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .const import PLATO_MAX, PLATO_MIN, UNIT_PLATO


def plato_to_sg(plato: float) -> float:
    """Convert degrees Plato to specific gravity.

    Standard brewing conversion. Water is 0 °P / 1.000 SG, so a device whose
    calibration polynomial emits Plato will read ~0 in water rather than ~1 --
    a difference that looks like a fault but is not one.
    """
    return 1.0 + plato / (258.6 - (plato / 258.2) * 227.1)


def sg_to_plato(sg: float) -> float:
    """Convert specific gravity to degrees Plato."""
    return (-1.0) * 616.868 + 1111.14 * sg - 630.272 * sg**2 + 135.997 * sg**3


def plato_in_range(plato: float) -> bool:
    """Return True if a Plato figure is physically plausible.

    Beyond this the conversion misbehaves and the device is not floating in
    anything -- typically it is lying on a bench.
    """
    return PLATO_MIN < plato < PLATO_MAX


def celsius(temperature: float, units: str) -> float:
    """Normalise a device temperature to Celsius."""
    unit = (units or "C").upper()
    if unit == "F":
        return (temperature - 32.0) * 5.0 / 9.0
    if unit == "K":
        return temperature - 273.15
    return temperature


@dataclass(slots=True)
class IspindelReading:
    """One decoded report from an iSpindel."""

    received: datetime
    name: str
    device_id: int
    token: str
    angle: float
    temperature: float
    temp_units: str
    battery: float
    rssi: int
    interval: int
    gravity_raw: float
    gravity_sg: float
    gravity_plato: float
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls, payload: dict[str, Any], input_unit: str, received: datetime
    ) -> IspindelReading:
        """Build a reading from the iSpindel's JSON body.

        Every field is optional except in practice; the device firmware varies
        by version and by service type, so nothing here may raise on a missing
        or malformed key.
        """

        def _float(key: str, default: float = 0.0) -> float:
            try:
                return float(payload.get(key, default))
            except (TypeError, ValueError):
                return default

        def _int(key: str, default: int = 0) -> int:
            try:
                return int(float(payload.get(key, default)))
            except (TypeError, ValueError):
                return default

        raw_gravity = _float("gravity")
        if input_unit == UNIT_PLATO:
            plato = raw_gravity
            sg = plato_to_sg(plato)
        else:
            sg = raw_gravity
            plato = sg_to_plato(sg)

        return cls(
            received=received,
            name=str(payload.get("name") or "iSpindel"),
            device_id=_int("ID"),
            token=str(payload.get("token") or ""),
            angle=_float("angle"),
            temperature=_float("temperature"),
            temp_units=str(payload.get("temp_units") or "C").upper(),
            battery=_float("battery"),
            rssi=_int("RSSI"),
            interval=_int("interval", 900) or 900,
            gravity_raw=raw_gravity,
            gravity_sg=round(sg, 4),
            gravity_plato=round(plato, 2),
            raw=dict(payload),
        )

    @property
    def temperature_celsius(self) -> float:
        """Temperature normalised to Celsius."""
        return round(celsius(self.temperature, self.temp_units), 2)

    @property
    def gravity_is_plausible(self) -> bool:
        """Whether the gravity figure is worth publishing."""
        return plato_in_range(self.gravity_plato)
