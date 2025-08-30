"""Config flow for the Interlogix/Hills ComNav UltraSync Hub."""
import logging
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType
import voluptuous as vol
import ultrasync

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    CONF_ONLINE,
    CONF_SERIAL_NUMBER,
    CONF_PASSCODE,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_ONLINE = False


class AuthFailureException(IOError):
    """A general exception we can use to track Authentication failures."""


def _as_bool(v) -> bool:
    """Coerce any stored value into a proper boolean."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "on")
    return bool(v)


def validate_input(hass: HomeAssistant, data: dict) -> bool:
    """Validate the user input allows us to connect."""
    usync = ultrasync.UltraSync(
        host=data[CONF_HOST],
        user=data[CONF_USERNAME],
        pin=data[CONF_PIN],
        online=data.get(CONF_ONLINE, False),
        serial_number=data.get(CONF_SERIAL_NUMBER),
        passcode=data.get(CONF_PASSCODE),
    )
    """Attempt to authenticate with the hub."""
    if not usync.login():
        raise AuthFailureException()
    return True


class UltraSyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """UltraSync config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return UltraSyncOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle user flow."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: Dict[str, str] = {}

        if user_input is not None:
            # ---- PIN validation ----
            pin = user_input.get(CONF_PIN, "")
            if not isinstance(pin, str):
                pin = str(pin)
            if not pin.isdigit():
                errors["pin"] = "invalid_pin"
            elif not (4 <= len(pin) <= 8):
                errors["pin"] = "invalid_pin_length"
            # ------------------------

            if errors:
                schema = vol.Schema(
                    {
                        vol.Optional(CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)): str,
                        vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                        vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")): str,
                        vol.Required(CONF_PIN, default=user_input.get(CONF_PIN, "")): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.PASSWORD)
                        ),
                        vol.Optional(CONF_ONLINE, default=_as_bool(user_input.get(CONF_ONLINE, DEFAULT_ONLINE))): bool,
                    }
                )
                return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

            # Always normalize boolean before saving
            user_input[CONF_ONLINE] = _as_bool(user_input.get(CONF_ONLINE, DEFAULT_ONLINE))

            if user_input[CONF_ONLINE]:
                self._user_input = user_input
                return await self.async_step_cloud()

            try:
                await self.hass.async_add_executor_job(validate_input, self.hass, user_input)
            except AuthFailureException:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PIN, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_ONLINE, default=DEFAULT_ONLINE): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_cloud(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle cloud login step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            all_data = {**self._user_input, **user_input}
            all_data[CONF_ONLINE] = _as_bool(all_data.get(CONF_ONLINE, DEFAULT_ONLINE))
            try:
                await self.hass.async_add_executor_job(validate_input, self.hass, all_data)
            except AuthFailureException:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")
            else:
                return self.async_create_entry(
                    title=all_data[CONF_HOST],
                    data=all_data,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL_NUMBER): str,
                vol.Required(CONF_PASSCODE): str,
            }
        )
        return self.async_show_form(step_id="cloud", data_schema=schema, errors=errors)


class UltraSyncOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle UltraSync client options."""

    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._user_input: Dict[str, Any] = {}

    async def async_step_init(self, user_input: Optional[ConfigType] = None):
        errors: Dict[str, str] = {}
        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            pin = user_input.get(CONF_PIN, "")
            if pin:
                if not isinstance(pin, str):
                    pin = str(pin)
                if not pin.isdigit():
                    errors["pin"] = "invalid_pin"
                elif not (4 <= len(pin) <= 8):
                    errors["pin"] = "invalid_pin_length"

            if errors:
                return self.async_show_form(step_id="init", data_schema=self._build_schema(current, user_input), errors=errors)

            # Normalize boolean
            user_input[CONF_ONLINE] = _as_bool(user_input.get(CONF_ONLINE, DEFAULT_ONLINE))

            if user_input[CONF_ONLINE]:
                self._user_input = user_input
                return await self.async_step_cloud()

            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=self._build_schema(current))

    def _build_schema(self, current: Dict[str, Any], override: Optional[Dict[str, Any]] = None):
        d = current if override is None else {**current, **override}
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): str,
                vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PIN, default=d.get(CONF_PIN, "")): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_ONLINE, default=_as_bool(d.get(CONF_ONLINE, DEFAULT_ONLINE))): bool,
                vol.Optional(CONF_SCAN_INTERVAL, default=d.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
            }
        )

    async def async_step_cloud(self, user_input: Optional[ConfigType] = None):
        """Handle cloud login options step.""" 
        if user_input is not None:
            all_data = {**self._user_input, **user_input}
            all_data[CONF_ONLINE] = _as_bool(all_data.get(CONF_ONLINE, DEFAULT_ONLINE))
            return self.async_create_entry(title="", data=all_data)

        current = {
            **self._config_entry.data,
            **self._config_entry.options,
            }
            
        schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL_NUMBER, default=current.get(CONF_SERIAL_NUMBER, "")): str,
                vol.Required(CONF_PASSCODE, default=current.get(CONF_PASSCODE, "")): str,
            }
        )
        return self.async_show_form(step_id="cloud", data_schema=schema)
