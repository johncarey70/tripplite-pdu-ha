"""Config flow for the Tripp Lite PDU integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TrippliteApiClient, TrippliteAuthError, TrippliteError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TripplitePduConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tripp Lite PDU."""

    VERSION = 1

    def is_matching(self, other_flow: config_entries.ConfigFlow) -> bool:
        """Return whether another flow matches this one."""
        return False

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass, verify_ssl=False)
            client = TrippliteApiClient(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session,
            )

            try:
                await client.async_test_auth()
            except TrippliteAuthError as err:
                _LOGGER.warning("Authentication failed for %s: %s", host, err)
                errors["base"] = "invalid_auth"
            except TrippliteError as err:
                _LOGGER.warning("Unable to connect to %s: %s", host, err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Tripp Lite PDU ({host})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
