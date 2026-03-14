"""Tripp Lite PDU integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_HOST, CONF_PASSWORD, CONF_USERNAME,
                                 Platform)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (TrippliteApiClient, TrippliteAuthError,
                  TrippliteConnectionError, TrippliteError)
from .coordinator import TrippliteCoordinator
from .utils import extract_firmware

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

type TrippliteConfigEntry = ConfigEntry[TrippliteCoordinator]


async def async_setup(_hass: HomeAssistant, _config: dict) -> bool:
    """Set up the integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TrippliteConfigEntry) -> bool:
    """Set up Tripp Lite PDU from a config entry."""

    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    _LOGGER.debug("Setting up Tripp Lite PDU %s", host)

    session = async_get_clientsession(hass, verify_ssl=False)
    client = TrippliteApiClient(host, username, password, session)
    coordinator = TrippliteCoordinator(hass, client, host)

    async def _initial_fetch(coro, default):
        """Fetch initial data, but fail explicitly on auth errors."""
        try:
            return await coro
        except TrippliteAuthError as err:
            _LOGGER.error("Authentication failed for Tripp Lite PDU %s: %s", host, err)
            raise
        except TrippliteConnectionError:
            return default
        except TrippliteError:
            return default

    device_info = await _initial_fetch(client.get_device_info(), {})
    variables = await _initial_fetch(client.get_variables(), {})
    loads = await _initial_fetch(client.get_loads(), {})

    firmware = extract_firmware(variables)

    coordinator.device_info_data = device_info
    coordinator.async_set_updated_data(
        {
            "loads": loads,
            "device_info": device_info,
            "variables": variables,
            "firmware": firmware,
        }
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TrippliteConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
