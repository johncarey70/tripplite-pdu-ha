"""Switch platform for the Tripp Lite PDU integration."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TrippliteCoordinator
from .const import DOMAIN, PDU_LOAD_COUNT


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Tripp Lite PDU switches."""

    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    loads = list(range(1, PDU_LOAD_COUNT + 1))

    entities = [TrippliteMainSwitch(coordinator, entry)]
    entities.extend(TrippliteSwitch(coordinator, entry, load_id) for load_id in loads)

    async_add_entities(entities, True)


# pylint: disable=abstract-method
class TrippliteSwitch(CoordinatorEntity[TrippliteCoordinator], SwitchEntity):
    """Representation of a PDU outlet."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TrippliteCoordinator, entry: ConfigEntry, load_id: int
    ) -> None:
        """Initialize outlet switch."""
        super().__init__(coordinator)
        self.entry = entry
        self.load_id = load_id

        self._attr_name = f"Load {load_id}"
        self._attr_unique_id = f"{entry.entry_id}_load_{load_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=f"Tripp Lite PDU {self.entry.data['host']}",
            manufacturer="Tripp Lite",
            model="PDUMH30HV19NET",
        )

    @property
    def is_on(self) -> bool:
        """Return outlet state."""
        state = self.coordinator.data.get(self.load_id)
        return state == "LOAD_STATE_ON"

    async def async_turn_on(self, **kwargs):
        """Turn outlet on."""
        await self.coordinator.async_set_load(self.load_id, True)

    async def async_turn_off(self, **kwargs):
        """Turn outlet off."""
        await self.coordinator.async_set_load(self.load_id, False)


# pylint: disable=abstract-method
class TrippliteMainSwitch(CoordinatorEntity[TrippliteCoordinator], SwitchEntity):
    """Representation of the main PDU load."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TrippliteCoordinator, entry: ConfigEntry) -> None:
        """Initialize main load switch."""
        super().__init__(coordinator)
        self.entry = entry

        self._attr_name = "00 Main Load"
        self._attr_unique_id = f"{entry.entry_id}_main_load"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=f"Tripp Lite PDU {self.entry.data['host']}",
            manufacturer="Tripp Lite",
            model="PDUMH30HV19NET",
        )

    @property
    def is_on(self) -> bool:
        """Return main load state."""
        state = self.coordinator.data.get("main_load")
        return state == "LOAD_STATE_ON"

    async def async_turn_on(self, **kwargs):
        """Turn main load on."""
        await self.coordinator.async_set_main_load(True)

    async def async_turn_off(self, **kwargs):
        """Turn main load off."""
        await self.coordinator.async_set_main_load(False)
