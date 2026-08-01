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
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IspindelConfigEntry
from .coordinator import IspindelRuntime
from .entity import IspindelEntity

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
        IspindelSensor(runtime, description) for description in SENSORS
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
