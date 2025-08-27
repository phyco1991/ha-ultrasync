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
    CONF_ONLINE,
    CONF_SERIAL_NUMBER,
    CONF_PASSCODE,
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.typing import ConfigType
import ultrasync
import voluptuous as vol

from .const import DEFAULT_NAME, DEFAULT_SCAN_INTERVAL
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class AuthFailureException(IOError):
    """A general exception we can use to track Authentication failures."""


def validate_input(hass: HomeAssistant, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""

    usync = ultrasync.UltraSync(
        host=data[CONF_HOST], user=data[CONF_USERNAME], pin=data[CONF_PIN], online=data[CONF_ONLINE], serial_number=data[CONF_SERIAL_NUMBER], passcode=data[CONF_PASSCODE],
    )

    # validate by attempting to authenticate with our hub

    if not usync.login():
        # report our connection issue
        raise AuthFailureException()

    return True


class UltraSyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """UltraSync config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

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

        errors = {}

        if user_input is not None:
            if user_input.get(CONF_ONLINE, False):
                self._user_input = user_input
                return await self.async_step_cloud()
            else:
                try:
                    await self.hass.async_add_executor_job(
                        validate_input, self.hass, user_input
                    )

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

        schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PIN): str,
                    vol.Optional(CONF_ONLINE, default=False): bool
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

        async def async_step_cloud(
            self, user_input: Optional[ConfigType] = None
        ) -> Dict[str, Any]:
            """Handle cloud login step."""
            errors = {}

            if user_input is not None:
                all_data = {**self._user_input, **user_input}
                try:
                    await self.hass.async_add_executor_job(
                        validate_input, self.hass, all_data
                    )
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
        """Initialize options flow."""
        self.config_entry = config_entry
        self._user_input: Dict[str, Any] = {}

    async def async_step_init(self, user_input: Optional[ConfigType] = None):
        """Manage UltraSync options."""
        errors = {}
        
        if user_input is not None:
            if user_input.get(CONF_ONLINE, False):
                # Save first step data and go to cloud step if needed
                self._user_input = user_input
                return await self.async_step_cloud()
            else:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): int,
                vol.Optional(
                    CONF_ONLINE,
                    default=self.config_entry.options.get(CONF_ONLINE, False)
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
        
    async def async_step_cloud(self, user_input: Optional[ConfigType] = None):
        """Handle cloud login options step."""
        errors = {}

        if user_input is not None:
            # Merge first + second step and save
            all_data = {**self._user_input, **user_input}
            return self.async_create_entry(title="", data=all_data)

        # Cloud-specific fields
        schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL_NUMBER): str,
                vol.Required(CONF_PASSCODE): str,
            }
        )

        return self.async_show_form(step_id="cloud", data_schema=schema, errors=errors)
