"""Config flow for the iSpindel → Grainfather integration."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.components import webhook
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_FORWARD_MINUTES,
    CONF_GRAINFATHER_URL,
    CONF_INPUT_UNIT,
    CONF_OUTPUT_UNIT,
    CONF_STALE_MINUTES,
    CONF_WEBHOOK_ID,
    DEFAULT_FORWARD_MINUTES,
    DEFAULT_NAME,
    DEFAULT_STALE_MINUTES,
    DOMAIN,
    GRAVITY_UNITS,
    UNIT_SG,
)


def _unit_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=GRAVITY_UNITS,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="gravity_unit",
        )
    )


def _settings_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema shared by the initial flow and the options flow."""
    return vol.Schema(
        {
            vol.Required(
                CONF_GRAINFATHER_URL, default=defaults.get(CONF_GRAINFATHER_URL, "")
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            vol.Required(
                CONF_INPUT_UNIT, default=defaults.get(CONF_INPUT_UNIT, UNIT_SG)
            ): _unit_selector(),
            vol.Required(
                CONF_OUTPUT_UNIT, default=defaults.get(CONF_OUTPUT_UNIT, UNIT_SG)
            ): _unit_selector(),
            vol.Required(
                CONF_FORWARD_MINUTES,
                default=defaults.get(CONF_FORWARD_MINUTES, DEFAULT_FORWARD_MINUTES),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=180, step=1, mode=NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
            vol.Required(
                CONF_STALE_MINUTES,
                default=defaults.get(CONF_STALE_MINUTES, DEFAULT_STALE_MINUTES),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=2, max=1440, step=1, mode=NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
            # Optional so an existing device can keep the URL it already has --
            # reconfiguring an iSpindel means getting it back into AP mode,
            # which is worth avoiding once it is floating in a fermenter.
            vol.Optional(
                CONF_WEBHOOK_ID, default=defaults.get(CONF_WEBHOOK_ID, "")
            ): str,
        }
    )


WEBHOOK_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,255}$")


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    """Return a mapping of field → error key."""
    errors: dict[str, str] = {}
    parsed = urlparse(user_input.get(CONF_GRAINFATHER_URL, ""))
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        errors[CONF_GRAINFATHER_URL] = "invalid_url"
    if int(user_input[CONF_STALE_MINUTES]) <= int(user_input[CONF_FORWARD_MINUTES]):
        # Otherwise every reading is already stale by the time the timer fires
        # and nothing is ever forwarded.
        errors[CONF_STALE_MINUTES] = "stale_too_short"
    supplied_id = (user_input.get(CONF_WEBHOOK_ID) or "").strip()
    if supplied_id and not WEBHOOK_ID_RE.match(supplied_id):
        errors[CONF_WEBHOOK_ID] = "invalid_webhook_id"
    return errors


class IspindelGrainfatherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                self._data = {
                    CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                    **{k: v for k, v in user_input.items() if k != CONF_NAME},
                }
                self._data[CONF_WEBHOOK_ID] = (
                    user_input.get(CONF_WEBHOOK_ID) or ""
                ).strip() or webhook.async_generate_id()
                self._data[CONF_FORWARD_MINUTES] = int(
                    self._data[CONF_FORWARD_MINUTES]
                )
                self._data[CONF_STALE_MINUTES] = int(self._data[CONF_STALE_MINUTES])
                return await self.async_step_webhook()

        defaults = user_input or {}
        schema = _settings_schema(defaults).extend(
            {
                vol.Required(
                    CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
                ): str
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_webhook(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the URL the device must be pointed at, then finish."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._data[CONF_NAME], data=self._data
            )

        url = webhook.async_generate_url(self.hass, self._data[CONF_WEBHOOK_ID])
        parsed = urlparse(url)
        return self.async_show_form(
            step_id="webhook",
            data_schema=vol.Schema({}),
            description_placeholders={
                "url": url,
                "host": parsed.hostname or "",
                "port": str(parsed.port or (443 if parsed.scheme == "https" else 80)),
                "path": parsed.path,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return IspindelGrainfatherOptionsFlow()


class IspindelGrainfatherOptionsFlow(OptionsFlow):
    """Allow the settings to be changed after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                user_input[CONF_FORWARD_MINUTES] = int(
                    user_input[CONF_FORWARD_MINUTES]
                )
                user_input[CONF_STALE_MINUTES] = int(user_input[CONF_STALE_MINUTES])
                # Blank means "leave the webhook alone" rather than "generate a
                # new one", so clearing the box cannot silently orphan a device.
                user_input[CONF_WEBHOOK_ID] = (
                    user_input.get(CONF_WEBHOOK_ID) or ""
                ).strip() or self.config_entry.data[CONF_WEBHOOK_ID]
                return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(user_input or current),
            errors=errors,
        )
