"""Runtime for the iSpindel → Grainfather integration.

Owns the inbound webhook, the most recent reading, and the timer that replays
that reading to Grainfather.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError, ClientResponseError, ClientTimeout
from aiohttp.web import Request, Response
from homeassistant.components import webhook
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FORWARD_MINUTES,
    CONF_GRAINFATHER_URL,
    CONF_INPUT_UNIT,
    CONF_OUTPUT_UNIT,
    CONF_STALE_MINUTES,
    CONF_WEBHOOK_ID,
    DEFAULT_FORWARD_MINUTES,
    DEFAULT_OUTPUT_UNIT,
    DEFAULT_STALE_MINUTES,
    DOMAIN,
    GRAINFATHER_REPORTED_INTERVAL,
    MIN_OFFLINE_SECONDS,
    SIGNAL_NEW_READING,
    SIGNAL_UPLOAD_RESULT,
    UNIT_PLATO,
    UNIT_SG,
)
from .models import IspindelReading

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

UPLOAD_TIMEOUT = ClientTimeout(total=20)


@dataclass(slots=True)
class UploadResult:
    """Outcome of one attempt to post to Grainfather."""

    when: datetime
    status: int | None
    ok: bool
    detail: str


class IspindelRuntime:
    """Holds live state for one configured iSpindel."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the runtime."""
        self.hass = hass
        self.entry = entry
        self.last_reading: IspindelReading | None = None
        self.last_upload: UploadResult | None = None
        # Deliberately defaults to off. Uncalibrated bench readings reaching a
        # live brew session are far more annoying than an upload that has to be
        # switched on. The switch entity restores the user's choice on startup.
        self.forwarding_enabled = False
        self._unsub_timer: Any = None
        # The id we actually registered. Kept separate from the configured one
        # so that changing the webhook in the options flow still unregisters
        # the old hook on reload rather than the new one.
        self._registered_webhook_id: str | None = None

    # -- configuration -----------------------------------------------------

    def _opt(self, key: str, default: Any) -> Any:
        """Read an option, falling back to the original config data."""
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def webhook_id(self) -> str:
        """The webhook id the device posts to."""
        return self._opt(CONF_WEBHOOK_ID, self.entry.data[CONF_WEBHOOK_ID])

    @property
    def grainfather_url(self) -> str:
        """Grainfather ingest endpoint."""
        return self._opt(CONF_GRAINFATHER_URL, "")

    @property
    def input_unit(self) -> str:
        """Gravity unit the device reports in."""
        return self._opt(CONF_INPUT_UNIT, UNIT_SG)

    @property
    def output_unit(self) -> str:
        """Gravity unit to send to Grainfather."""
        return self._opt(CONF_OUTPUT_UNIT, DEFAULT_OUTPUT_UNIT)

    @property
    def forward_minutes(self) -> int:
        """How often to post to Grainfather."""
        return int(self._opt(CONF_FORWARD_MINUTES, DEFAULT_FORWARD_MINUTES))

    @property
    def stale_minutes(self) -> int:
        """How old a reading may be and still be worth forwarding."""
        return int(self._opt(CONF_STALE_MINUTES, DEFAULT_STALE_MINUTES))

    @property
    def webhook_url(self) -> str:
        """Full URL the iSpindel should be pointed at."""
        return webhook.async_generate_url(self.hass, self.webhook_id)

    # -- lifecycle ---------------------------------------------------------

    async def async_start(self) -> None:
        """Register the webhook and start the forwarding timer."""
        webhook_id = self.webhook_id
        webhook.async_register(
            self.hass,
            DOMAIN,
            "iSpindel",
            webhook_id,
            self._handle_webhook,
            allowed_methods=["POST"],
            local_only=True,
        )
        self._registered_webhook_id = webhook_id
        self._unsub_timer = async_track_time_interval(
            self.hass,
            self._handle_timer,
            timedelta(minutes=self.forward_minutes),
        )
        _LOGGER.debug(
            "Started; webhook %s, forwarding every %s min",
            self.webhook_id,
            self.forward_minutes,
        )

    @callback
    def async_stop(self) -> None:
        """Tear down the webhook and timer."""
        if self._registered_webhook_id is not None:
            webhook.async_unregister(self.hass, self._registered_webhook_id)
            self._registered_webhook_id = None
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    # -- inbound -----------------------------------------------------------

    async def _handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response:
        """Accept one POST from the iSpindel."""
        try:
            payload = await request.json()
        except ValueError:
            _LOGGER.warning("Ignoring malformed JSON from iSpindel")
            return Response(status=400)

        if not isinstance(payload, dict):
            _LOGGER.warning("Ignoring non-object payload from iSpindel: %r", payload)
            return Response(status=400)

        self.last_reading = IspindelReading.from_payload(
            payload, self.input_unit, dt_util.utcnow()
        )
        async_dispatcher_send(self.hass, f"{SIGNAL_NEW_READING}_{self.entry.entry_id}")
        return Response(status=200)

    # -- outbound ----------------------------------------------------------

    @property
    def reading_is_fresh(self) -> bool:
        """Whether the last reading is recent enough to be worth sending."""
        if self.last_reading is None:
            return False
        age = (dt_util.utcnow() - self.last_reading.received).total_seconds()
        return age < self.stale_minutes * 60

    @property
    def is_online(self) -> bool:
        """Whether the device is still reporting.

        Uses the device's own stated interval so this works whether it wakes
        every minute or every quarter of an hour.
        """
        if self.last_reading is None:
            return False
        age = (dt_util.utcnow() - self.last_reading.received).total_seconds()
        allowed = max(self.last_reading.interval * 3, MIN_OFFLINE_SECONDS)
        return age < allowed

    def build_payload(self) -> dict[str, Any] | None:
        """Build the iSpindel-format body Grainfather expects."""
        reading = self.last_reading
        if reading is None:
            return None

        gravity = (
            reading.gravity_plato
            if self.output_unit == UNIT_PLATO
            else reading.gravity_sg
        )
        return {
            "name": reading.name,
            "ID": reading.device_id,
            "token": reading.token,
            "angle": round(reading.angle, 4),
            "temperature": round(reading.temperature, 3),
            "temp_units": reading.temp_units,
            "battery": round(reading.battery, 3),
            "gravity": gravity,
            # Grainfather is told the cadence it actually sees, not the rate the
            # device talks to Home Assistant.
            "interval": GRAINFATHER_REPORTED_INTERVAL,
            "RSSI": reading.rssi,
        }

    async def _handle_timer(self, _now: datetime) -> None:
        """Forward on the timer, if everything says we should."""
        if not self.forwarding_enabled:
            return
        if not self.reading_is_fresh:
            _LOGGER.debug("Skipping upload: no fresh reading")
            return
        await self.async_upload()

    async def async_upload(self) -> UploadResult:
        """Post the most recent reading to Grainfather."""
        payload = self.build_payload()
        now = dt_util.utcnow()

        if payload is None:
            result = UploadResult(now, None, False, "no reading")
        elif not self.grainfather_url:
            result = UploadResult(now, None, False, "no url configured")
        else:
            session = async_get_clientsession(self.hass)
            try:
                async with session.post(
                    self.grainfather_url,
                    json=payload,
                    timeout=UPLOAD_TIMEOUT,
                ) as response:
                    ok = response.status < 300
                    result = UploadResult(
                        now, response.status, ok, "ok" if ok else response.reason or ""
                    )
                    if not ok:
                        _LOGGER.warning(
                            "Grainfather rejected the upload: HTTP %s", response.status
                        )
            except ClientResponseError as err:
                result = UploadResult(now, err.status, False, str(err))
                _LOGGER.warning("Grainfather upload failed: %s", err)
            except (ClientError, TimeoutError) as err:
                # A transient network problem must never wedge the timer.
                result = UploadResult(now, None, False, str(err) or type(err).__name__)
                _LOGGER.warning("Grainfather upload failed: %s", err)

        self.last_upload = result
        async_dispatcher_send(self.hass, f"{SIGNAL_UPLOAD_RESULT}_{self.entry.entry_id}")
        return result
