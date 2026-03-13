"""Config flow for the Tripp Lite PDU integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .api import TrippliteApiClient, TrippliteError
from .const import DOMAIN


class TripplitePduConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Tripp Lite PDU."""

    VERSION = 1

    def is_matching(self, _other_flow):
        """Return whether another flow matches this one."""
        return False

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""

        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            client = TrippliteApiClient(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            try:
                await client.async_test_auth()
            except TrippliteError:
                errors["base"] = "cannot_connect"
            else:
                await client.session.close()
                return self.async_create_entry(
                    title=f"Tripp Lite PDU ({host})",
                    data=user_input,
                )
            finally:
                if not client.session.closed:
                    await client.session.close()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
