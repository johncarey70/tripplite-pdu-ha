"""Data coordinator for the Tripp Lite PDU integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)

from .api import (TrippliteApiClient, TrippliteAuthError,
                  TrippliteConnectionError, TrippliteError)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, PDU_COMMAND_DELAY
from .utils import extract_firmware

_LOGGER = logging.getLogger(__name__)

type TrippliteData = dict[str, object]


class TrippliteCoordinator(DataUpdateCoordinator[TrippliteData]):
    """Coordinate Tripp Lite PDU data and commands."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TrippliteApiClient,
        host: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.host = host
        self.command_lock = asyncio.Lock()
        self.device_info_data: dict[str, str | int | bool] = {}

    async def _async_wait_for_state(
        self,
        key: int | str,
        expected_state: str,
    ) -> TrippliteData:
        """Wait until the requested state is reported or timeout expires."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + PDU_COMMAND_DELAY

        device_info = self.device_info_data
        variables = self.data.get("variables", {}) if self.data is not None else {}
        firmware = self.data.get("firmware") if self.data is not None else None

        while True:
            try:
                loads = await self.client.get_loads()
            except TrippliteAuthError as err:
                raise UpdateFailed(
                    f"Authentication failed for {self.host}: {err}"
                ) from err
            except TrippliteConnectionError as err:
                raise UpdateFailed(
                    f"Error communicating with {self.host}: {err}"
                ) from err
            except TrippliteError as err:
                raise UpdateFailed(
                    f"Unexpected API error from {self.host}: {err}"
                ) from err

            if loads.get(key) == expected_state:
                return {
                    "loads": loads,
                    "device_info": device_info,
                    "variables": variables,
                    "firmware": firmware,
                }

            if loop.time() >= deadline:
                return {
                    "loads": loads,
                    "device_info": device_info,
                    "variables": variables,
                    "firmware": firmware,
                }

            await asyncio.sleep(0.75)

    async def _async_update_data(self) -> TrippliteData:
        """Fetch the latest device data."""
        async with self.command_lock:
            try:
                loads = await self.client.get_loads()
                variables = await self.client.get_variables()

                firmware = extract_firmware(variables)

                if not self.device_info_data:
                    self.device_info_data = await self.client.get_device_info()

            except TrippliteAuthError as err:
                raise UpdateFailed(
                    f"Authentication failed for {self.host}: {err}"
                ) from err
            except TrippliteConnectionError as err:
                raise UpdateFailed(
                    f"Error communicating with {self.host}: {err}"
                ) from err
            except TrippliteError as err:
                raise UpdateFailed(
                    f"Unexpected API error from {self.host}: {err}"
                ) from err

            return {
                "loads": loads,
                "device_info": self.device_info_data,
                "variables": variables,
                "firmware": firmware,
            }

    async def async_set_load(self, load_id: int, turn_on: bool) -> None:
        """Set an outlet state."""
        expected_state = "LOAD_STATE_ON" if turn_on else "LOAD_STATE_OFF"

        async with self.command_lock:
            await self.client.set_load(load_id, turn_on)
            self.async_set_updated_data(
                await self._async_wait_for_state(load_id, expected_state)
            )

    async def async_set_main_load(self, turn_on: bool) -> None:
        """Set the main load state."""
        expected_state = "LOAD_STATE_ON" if turn_on else "LOAD_STATE_OFF"

        async with self.command_lock:
            await self.client.set_main_load(turn_on)
            self.async_set_updated_data(
                await self._async_wait_for_state("main_load", expected_state)
            )
