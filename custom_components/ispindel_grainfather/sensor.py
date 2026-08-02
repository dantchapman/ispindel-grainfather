"""Sensor entities for the iSpindel → Grainfather integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import IspindelConfigEntry
from .const import ABV_FACTOR
from .coordinator import IspindelRuntime
from .entity import IspindelEntity
from .session import BrewSession
from .session_entity import BrewSessionEntity

UNIT_SPECIFIC_GRAVITY = "SG"
UNIT_DEGREES_PLATO = "°P"


@dataclass(frozen=True, kw_only=True)
class IspindelSensorDescription(SensorEntityDescription):
    """Describes an iSpindel sensor."""

    value_fn: Callable[[IspindelRuntime], Any]
    available_fn: Callable[[IspindelRuntime], bool] = lambda runtime: (
        runtime.last_reading is not None and runtime.is_online
    )
    attributes_fn: Callable[[IspindelRuntime], dict[str, Any]] | None = None


def _always(_runtime: IspindelRuntime) -> bool:
    return True


SENSORS: tuple[IspindelSensorDescription, ...] = (
    IspindelSensorDescription(
        key="gravity",
        translation_key="gravity",
        native_unit_of_measurement=UNIT_SPECIFIC_GRAVITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        icon="mdi:water-percent",
        value_fn=lambda runtime: runtime.last_reading.gravity_sg,
        # An implausible figure means the device is not floating in anything.
        available_fn=lambda runtime: (
            runtime.last_reading is not None
            and runtime.is_online
            and runtime.last_reading.gravity_is_plausible
        ),
    ),
    IspindelSensorDescription(
        key="gravity_plato",
        translation_key="gravity_plato",
        native_unit_of_measurement=UNIT_DEGREES_PLATO,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:water-percent",
        value_fn=lambda runtime: runtime.last_reading.gravity_plato,
        available_fn=lambda runtime: (
            runtime.last_reading is not None
            and runtime.is_online
            and runtime.last_reading.gravity_is_plausible
        ),
    ),
    IspindelSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda runtime: runtime.last_reading.temperature_celsius,
    ),
    IspindelSensorDescription(
        key="angle",
        translation_key="angle",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:angle-acute",
        value_fn=lambda runtime: round(runtime.last_reading.angle, 3),
    ),
    IspindelSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda runtime: round(runtime.last_reading.battery, 3),
    ),
    IspindelSensorDescription(
        key="signal",
        translation_key="signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Enabled by default: an iSpindel usually ends up inside a fermenter in
        # a fridge, where marginal signal is a common cause of missing readings
        # and is the first thing worth looking at when reports stop arriving.
        value_fn=lambda runtime: runtime.last_reading.rssi,
    ),
    IspindelSensorDescription(
        key="last_report",
        translation_key="last_report",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-check-outline",
        available_fn=lambda runtime: runtime.last_reading is not None,
        value_fn=lambda runtime: runtime.last_reading.received,
        attributes_fn=lambda runtime: {
            "device_name": runtime.last_reading.name,
            "device_id": runtime.last_reading.device_id,
            "reported_interval": runtime.last_reading.interval,
            "gravity_raw": runtime.last_reading.gravity_raw,
            "temperature_raw": runtime.last_reading.temperature,
            "temp_units": runtime.last_reading.temp_units,
        },
    ),
    IspindelSensorDescription(
        key="last_upload",
        translation_key="last_upload",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:cloud-upload-outline",
        available_fn=lambda runtime: runtime.last_upload is not None,
        value_fn=lambda runtime: runtime.last_upload.when,
        attributes_fn=lambda runtime: {
            "status": runtime.last_upload.status,
            "ok": runtime.last_upload.ok,
            "detail": runtime.last_upload.detail,
        },
    ),
    IspindelSensorDescription(
        key="webhook_url",
        translation_key="webhook_url",
        icon="mdi:link-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        available_fn=_always,
        value_fn=lambda runtime: runtime.webhook_url,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IspindelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    runtime = entry.runtime_data
    async_add_entities(
        [IspindelSensor(runtime, d) for d in SENSORS]
        + [BrewSessionSensor(runtime, d) for d in SESSION_SENSORS]
    )


class IspindelSensor(IspindelEntity, SensorEntity):
    """A single value from the iSpindel."""

    entity_description: IspindelSensorDescription

    def __init__(
        self, runtime: IspindelRuntime, description: IspindelSensorDescription
    ) -> None:
        """Initialise the sensor."""
        super().__init__(runtime, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Whether this reading currently means anything."""
        return self.entity_description.available_fn(self.runtime)

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        if not self.available:
            return None
        return self.entity_description.value_fn(self.runtime)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return provenance for the raw device fields."""
        if self.entity_description.attributes_fn is None or not self.available:
            return None
        return self.entity_description.attributes_fn(self.runtime)


# =============================================================================
# Brew session sensors. These describe the *viewed* session, so the chart and
# the figures beside it always agree about which brew is on screen.
# =============================================================================


def _finish(runtime: IspindelRuntime, session: BrewSession) -> float | None:
    """Gravity to measure a session against: stored FG, or live if running."""
    if session.fg is not None:
        return session.fg
    return runtime.current_gravity if session.is_active else None


@dataclass(frozen=True, kw_only=True)
class BrewSensorDescription(SensorEntityDescription):
    """Describes a brew session sensor."""

    value_fn: Callable[[IspindelRuntime, BrewSession], Any]
    attributes_fn: Callable[[IspindelRuntime, BrewSession], dict[str, Any]] | None = None


def _elapsed_days(runtime: IspindelRuntime, s: BrewSession) -> float | None:
    start = s.pitched_dt
    if start is None:
        return None
    finish = s.ended_dt or dt_util.utcnow()
    return round(max(0.0, (finish - start).total_seconds() / 86400), 2)


def _attenuation(runtime: IspindelRuntime, s: BrewSession) -> float | None:
    fg = _finish(runtime, s)
    if s.og is None or fg is None or s.og <= 1.0:
        return None
    return round(((s.og - fg) / (s.og - 1.0)) * 100, 1)


def _abv(runtime: IspindelRuntime, s: BrewSession) -> float | None:
    fg = _finish(runtime, s)
    if s.og is None or fg is None:
        return None
    return round((s.og - fg) * ABV_FACTOR, 2)


SESSION_SENSORS: tuple[BrewSensorDescription, ...] = (
    BrewSensorDescription(
        key="start",
        translation_key="session_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:beaker-plus-outline",
        value_fn=lambda r, s: s.pitched_dt,
    ),
    BrewSensorDescription(
        key="end",
        translation_key="session_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:beaker-check-outline",
        # While fermenting there is no end yet; the chart treats "now" as the
        # right-hand edge, so report now rather than going unavailable.
        value_fn=lambda r, s: s.ended_dt or dt_util.utcnow(),
        attributes_fn=lambda r, s: {"fermenting": s.is_active},
    ),
    BrewSensorDescription(
        key="name",
        translation_key="session_name",
        icon="mdi:glass-mug-variant",
        value_fn=lambda r, s: s.name[:255],
        attributes_fn=lambda r, s: {
            "recipe_url": s.recipe_url,
            "session_id": s.id,
            "fermenting": s.is_active,
        },
    ),
    BrewSensorDescription(
        key="og",
        translation_key="session_og",
        native_unit_of_measurement=UNIT_SPECIFIC_GRAVITY,
        suggested_display_precision=4,
        icon="mdi:water-percent",
        value_fn=lambda r, s: s.og,
    ),
    BrewSensorDescription(
        key="fg",
        translation_key="session_fg",
        native_unit_of_measurement=UNIT_SPECIFIC_GRAVITY,
        suggested_display_precision=4,
        icon="mdi:water-percent",
        value_fn=_finish,
    ),
    BrewSensorDescription(
        key="elapsed",
        translation_key="session_elapsed",
        native_unit_of_measurement="d",
        suggested_display_precision=2,
        icon="mdi:timer-sand",
        value_fn=_elapsed_days,
    ),
    BrewSensorDescription(
        key="attenuation",
        translation_key="session_attenuation",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        icon="mdi:chart-line-variant",
        value_fn=_attenuation,
    ),
    BrewSensorDescription(
        key="abv",
        translation_key="session_abv",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
        icon="mdi:percent-outline",
        value_fn=_abv,
    ),
)


class BrewSessionSensor(BrewSessionEntity, SensorEntity):
    """One figure describing the viewed brew session."""

    entity_description: BrewSensorDescription

    def __init__(
        self, runtime: IspindelRuntime, description: BrewSensorDescription
    ) -> None:
        """Initialise the sensor."""
        super().__init__(runtime, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Available once a session exists and the figure can be computed."""
        session = self.viewed
        if session is None:
            return False
        return self.entity_description.value_fn(self.runtime, session) is not None

    @property
    def native_value(self) -> Any:
        """Return the value for the viewed session."""
        session = self.viewed
        if session is None:
            return None
        return self.entity_description.value_fn(self.runtime, session)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra context for the viewed session."""
        session = self.viewed
        if session is None or self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.runtime, session)
