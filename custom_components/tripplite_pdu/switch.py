"""Switch platform for the Tripp Lite PDU integration."""

from abc import ABC

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TrippliteConfigEntry
from .const import PDU_LOAD_COUNT
from .coordinator import TrippliteCoordinator
from .entity import TrippliteEntity
from .utils import get_pdu_slug


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TrippliteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tripp Lite PDU switches."""
    coordinator: TrippliteCoordinator = entry.runtime_data
    host = entry.data["host"]

    entities: list[TrippliteBaseSwitch] = [
        TrippliteMainSwitch(coordinator, host, entry.entry_id)
    ]
    entities.extend(
        TrippliteLoadSwitch(coordinator, host, entry.entry_id, load_id)
        for load_id in range(1, PDU_LOAD_COUNT + 1)
    )

    async_add_entities(entities, update_before_add=True)


# pylint: disable=abstract-method,too-many-ancestors
class TrippliteBaseSwitch(TrippliteEntity, SwitchEntity, ABC):
    """Base class for Tripp Lite switches."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: TrippliteCoordinator,
        host: str,
        unique_id: str,
        name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, host)
        self._attr_name = name
        self._attr_unique_id = unique_id

    def _get_load_state(self, key: int | str) -> bool:
        """Return the state for a load."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            return False

        loads = data.get("loads")
        if not isinstance(loads, dict):
            return False

        return loads.get(key) == "LOAD_STATE_ON"


# pylint: disable=abstract-method,too-many-ancestors
class TrippliteLoadSwitch(TrippliteBaseSwitch):
    """Representation of a PDU outlet."""

    def __init__(
        self,
        coordinator: TrippliteCoordinator,
        host: str,
        entry_id: str,
        load_id: int,
    ) -> None:
        """Initialize the outlet switch."""
        super().__init__(
            coordinator=coordinator,
            host=host,
            unique_id=f"{entry_id}_load_{load_id}",
            name=f"Outlet {load_id}",
        )
        self._load_id = load_id

    @property
    def suggested_object_id(self) -> str:
        """Return suggested entity object id."""
        slug = get_pdu_slug(self._host, self.coordinator.device_info_data)
        return f"{slug}_outlet_{self._load_id}"

    @property
    def is_on(self) -> bool:
        """Return outlet state."""
        return self._get_load_state(self._load_id)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn outlet on."""
        await self.coordinator.async_set_load(self._load_id, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn outlet off."""
        await self.coordinator.async_set_load(self._load_id, False)


# pylint: disable=abstract-method,too-many-ancestors
class TrippliteMainSwitch(TrippliteBaseSwitch):
    """Representation of the main PDU load."""

    def __init__(
        self,
        coordinator,
        host: str,
        entry_id: str,
    ) -> None:
        """Initialize the main load switch."""
        super().__init__(
            coordinator=coordinator,
            host=host,
            unique_id=f"{entry_id}_main_load",
            name="Main Load",
        )

    @property
    def suggested_object_id(self) -> str:
        """Return suggested entity object id."""
        slug = get_pdu_slug(self._host, self.coordinator.device_info_data)
        return f"{slug}_main_load"

    @property
    def is_on(self) -> bool:
        """Return main load state."""
        return self._get_load_state("main_load")

    async def async_turn_on(self, **kwargs) -> None:
        """Turn main load on."""
        await self.coordinator.async_set_main_load(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn main load off."""
        await self.coordinator.async_set_main_load(False)
