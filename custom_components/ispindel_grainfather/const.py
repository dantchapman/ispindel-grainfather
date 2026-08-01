"""Constants for the iSpindel → Grainfather integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ispindel_grainfather"

CONF_GRAINFATHER_URL: Final = "grainfather_url"
CONF_FORWARD_MINUTES: Final = "forward_minutes"
CONF_INPUT_UNIT: Final = "input_unit"
CONF_OUTPUT_UNIT: Final = "output_unit"
CONF_STALE_MINUTES: Final = "stale_minutes"
CONF_WEBHOOK_ID: Final = "webhook_id"

UNIT_SG: Final = "sg"
UNIT_PLATO: Final = "plato"
GRAVITY_UNITS: Final = [UNIT_SG, UNIT_PLATO]

DEFAULT_NAME: Final = "iSpindel"
DEFAULT_FORWARD_MINUTES: Final = 15
DEFAULT_STALE_MINUTES: Final = 30

# The iSpindel is expected to report at least this often before we consider it
# offline; the device tells us its own interval, and we allow three missed
# reports before complaining, with this as a floor for fast-reporting devices.
MIN_OFFLINE_SECONDS: Final = 300

# Grainfather rejects nothing, but this is the cadence it is told it is seeing,
# and matches the interval iSpindel's own documentation recommends.
GRAINFATHER_REPORTED_INTERVAL: Final = 900

# Outside this Plato range the Plato→SG conversion approaches a divide-by-zero
# and the reading is meaningless anyway (the device is not floating).
PLATO_MIN: Final = -5.0
PLATO_MAX: Final = 50.0

SIGNAL_NEW_READING: Final = f"{DOMAIN}_new_reading"
SIGNAL_UPLOAD_RESULT: Final = f"{DOMAIN}_upload_result"
