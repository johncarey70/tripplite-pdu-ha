"""Tripp Lite PDU integration."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_HOST, CONF_PASSWORD, CONF_USERNAME,
                                 Platform)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import TrippliteApiClient, TrippliteError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, PDU_COMMAND_DELAY

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH]


class TrippliteCoordinator(DataUpdateCoordinator[dict[int | str, str]]):
    """Coordinate Tripp Lite PDU data and commands."""

    def __init__(self, hass: HomeAssistant, client: TrippliteApiClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="tripplite_pdu",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.command_lock = asyncio.Lock()

    async def _async_wait_for_state(
        self,
        key: int | str,
        expected_state: str,
    ) -> dict[int | str, str]:
        """Wait until the requested state is reported or timeout expires."""

        loop = asyncio.get_running_loop()
        deadline = loop.time() + PDU_COMMAND_DELAY

        while True:
            data = await self.client.get_loads()

            if data.get(key) == expected_state:
                return data

            if loop.time() >= deadline:
                return data

            await asyncio.sleep(0.75)

    async def _async_update_data(self) -> dict[int | str, str]:
        """Fetch data from the device."""
        async with self.command_lock:
            return await self.client.get_loads()

    async def async_set_load(self, load_id: int, turn_on: bool) -> None:
        """Set outlet state."""
        expected_state = "LOAD_STATE_ON" if turn_on else "LOAD_STATE_OFF"

        async with self.command_lock:
            await self.client.set_load(load_id, turn_on)
            self.async_set_updated_data(
                await self._async_wait_for_state(load_id, expected_state)
            )

    async def async_set_main_load(self, turn_on: bool) -> None:
        """Set main load state."""
        expected_state = "LOAD_STATE_ON" if turn_on else "LOAD_STATE_OFF"

        async with self.command_lock:
            await self.client.set_main_load(turn_on)
            self.async_set_updated_data(
                await self._async_wait_for_state("main_load", expected_state)
            )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tripp Lite PDU from config entry."""

    client = TrippliteApiClient(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    coordinator = TrippliteCoordinator(hass, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except TrippliteError as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to Tripp Lite PDU {entry.data[CONF_HOST]}"
        ) from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data: dict = hass.data[DOMAIN].pop(entry.entry_id, None)

        if data:
            client: TrippliteApiClient = data.get("client")
            if client and client.session:
                await client.session.close()

    return unload_ok
